/* Memory card files for replays and settings (research/phase46), through the game's own libmc (Sony XMCSERV client,
 * statically linked; the IOP modules are the game's). Never touches the game's save folder BISLPM-66301.
 *
 * libmc in the executable (each issues one RPC to XMCSERV; the command number identifies it):
 *   0x00155558 sceMcGetInfo(port, slot, &type, &free, &format)   cmd 1
 *   0x00154DD0 sceMcOpen(port, slot, name, mode)                  cmd 2   (0x00154EF8 sceMcMkdir: open with 0x40)
 *   0x00154F30 sceMcClose(fd)                                     cmd 3
 *   0x00155150 sceMcRead(fd, buf, size)                           cmd 5
 *   0x00155268 sceMcWrite(fd, buf, size)                          cmd 6
 *   0x00155EC0 sceMcRename(port, slot, path, new_entry_name)      cmd 14 (set file info, name flag 0x10)
 *   0x00155B28 sceMcDelete(port, slot, path)                      cmd 15
 *   0x00155420 sceMcSync(mode, &cmd, &result): mode 1 polls; 1 = finished, 0 = running, -1 = nothing pending
 *
 * One command may be outstanding at a time and the game's own save manager (state 0x00339D50, 3 while a job runs)
 * polls sceMcSync from its card thread, so a job only starts while that manager is idle and the caller must only
 * run jobs where the game does not start card work (our own screens).
 *
 * Writes are atomic for the caller: a file is written as NAME.TMP, closed, read back and compared, and only then is
 * the old NAME deleted and NAME.TMP renamed to NAME. A power cut leaves either the old NAME, or a complete verified
 * NAME.TMP (mc_load falls back to it), never a half-written NAME. The folder gets icon.sys and the game's icon
 * (embedded in the executable at 0x001D4DB0, 33,704 bytes) when it is first created. */
#include "ibara_ps2.h"

#define MC_GETINFO 0x00155558u
#define MC_OPEN    0x00154DD0u
#define MC_MKDIR   0x00154EF8u
#define MC_CLOSE   0x00154F30u
#define MC_READ    0x00155150u
#define MC_WRITE   0x00155268u
#define MC_RENAME  0x00155EC0u
#define MC_DELETE  0x00155B28u
#define MC_SYNC    0x00155420u
#define MC_GETDIR  0x00155748u /* sceMcGetDir(port, slot, pattern, mode, max, table): 64-byte entries, name at +0x20 */
#define GAME_MC_STATE 0x00339D50u

#define ICON_SYS_TEMPLATE 0x001D49B0u /* the game's icon.sys, 964 bytes */
#define ICON_SYS_SIZE     964u
#define ICON_DATA         0x001D4DB0u /* ibara.ico */
#define ICON_SIZE         0x83A8u

#define MC_RDONLY 0x0001
#define MC_WRONLY 0x0002
#define MC_CREAT  0x0200

#define CHUNK 0x4000u /* bytes per read / write command (one per frame) */
#define WORK  ((u8 *)0x01E80000u) /* read-back and icon.sys buffer, 64-byte aligned; unused RAM in the frontend and in games */

/* Each replay is its own save (folder BISLPM-66301R<date>), so it can be copied to and from PCSX2 or another card
 * on its own; settings and scores live in BISLPM-66301KURO. The caller names the folder and the browser title. */

typedef s32 (*fn3)(s32, s32, s32);
typedef s32 (*fn4)(s32, s32, s32, s32);
typedef s32 (*fn5)(s32, s32, s32, s32, s32);

enum { ST_IDLE, ST_INFO, ST_MKDIR, ST_ISYS_OPEN, ST_ISYS_WRITE, ST_ISYS_CLOSE, ST_ICO_OPEN, ST_ICO_WRITE, ST_ICO_CLOSE,
       ST_DEL_TMP, ST_OPEN_TMP, ST_WRITE, ST_CLOSE, ST_VOPEN, ST_VREAD, ST_VCLOSE, ST_DEL_OLD, ST_RENAME,
       ST_LOPEN, ST_LOPEN_TMP, ST_LREAD, ST_LCLOSE, ST_DIR, ST_DONE, ST_FAIL };

struct mc_job {
	u32 state, waiting, pos, size, max, fd;
	s32 result, error; /* error: the failing step << 16 | (result & 0xFFFF) */
	s32 type, free, format;
	const u8 *src;
	u8 *dst;
	char dir[40], path[80], tmp[80], name[32], isys[80], ico[80];
	const u8 *title; /* Shift-JIS browser title (two lines, break after title_break bytes), 0-terminated, <= 68 bytes */
	u32 title_break;
};
static struct mc_job job;
u32 mc_log[4]; /* last error, steps run, writes, verifies (debug) */

static void join(char *d, const char *a, const char *b)
{
	while (*a)
		*d++ = *a++;
	while (*b)
		*d++ = *b++;
	*d = 0;
}

static void fail(void)
{
	job.error = (s32)(job.state << 16 | ((u32)job.result & 0xFFFFu));
	mc_log[0] = (u32)job.error;
	job.state = ST_FAIL;
}

/* issue: the libmc call returned; 0 means the command is queued */
static u32 issued;
static void issue(s32 r)
{
	issued++;
	if (r != 0) {
		job.result = r;
		fail();
	} else {
		job.waiting = 1;
	}
}

/* 1 while the command is still running; else the result is in job.result */
static u32 busy(void)
{
	s32 cmd, res;
	if (!job.waiting)
		return 0;
	if (((fn3)MC_SYNC)(1, (s32)&cmd, (s32)&res) != 1)
		return 1;
	job.waiting = 0;
	job.result = res;
	return 0;
}

static s32 mc_open(const char *p, s32 mode) { return ((fn4)MC_OPEN)(0, 0, (s32)p, mode); }

u32 mc_busy(void) { return job.state != ST_IDLE && job.state != ST_DONE && job.state != ST_FAIL; }
s32 mc_error(void) { return job.state == ST_FAIL ? job.error : 0; }
u32 mc_done(void) { return job.state == ST_DONE; }
u32 mc_loaded(void) { return job.size; }

static u32 start(const char *dir, const char *name)
{
	if (mc_busy() || EE_RAM(u32, GAME_MC_STATE) == 3u)
		return 0;
	job.waiting = job.pos = 0;
	job.error = 0;
	join(job.dir, "/", dir);
	join(job.path, job.dir, "/");
	{
		char *p = job.path;
		while (*p)
			p++;
		join(p, name, "");
	}
	join(job.isys, job.dir, "/icon.sys");
	join(job.ico, job.dir, "/ibara.ico");
	join(job.tmp, job.path, ".TMP");
	join(job.name, name, "");
	return 1;
}

/* Saves size bytes from src as /dir/name; a new folder gets icon.sys with the given Shift-JIS title (line break after
 * title_break bytes) and the game's icon. src and title must stay unchanged until mc_done() or mc_error(). */
u32 mc_save(const char *dir, const char *name, const void *src, u32 size, const u8 *title, u32 title_break)
{
	if (!start(dir, name))
		return 0;
	job.src = (const u8 *)src;
	job.title = title;
	job.title_break = title_break;
	job.size = size;
	job.state = ST_INFO;
	return 1;
}

/* Loads DIR/name (or its verified NAME.TMP if a save was cut before the swap) into dst, up to max bytes;
 * mc_loaded() gives the size read. The caller checks the contents (header, checksum). */
/* Lists the entries matching pattern (e.g. "/BISLPM-66301R*") into table (max entries of 64 bytes, name at +0x20,
 * 64-byte aligned); mc_loaded() gives the count. */
u32 mc_list(const char *pattern, void *table, u32 max)
{
	if (mc_busy() || EE_RAM(u32, GAME_MC_STATE) == 3u)
		return 0;
	job.waiting = job.pos = 0;
	job.error = 0;
	join(job.path, pattern, "");
	job.dst = (u8 *)table;
	job.max = max;
	job.size = 0;
	job.state = ST_DIR;
	return 1;
}

u32 mc_load(const char *dir, const char *name, void *dst, u32 max)
{
	if (!start(dir, name))
		return 0;
	job.dst = (u8 *)dst;
	job.max = max;
	job.size = 0;
	job.state = ST_LOPEN;
	return 1;
}

static void icon_sys(void)
{
	u32 i, end = 0;
	for (i = 0; i < ICON_SYS_SIZE; i++)
		WORK[i] = EE_RAM(u8, ICON_SYS_TEMPLATE + i); /* the game's icon.sys (colours, lights, icon names) */
	while (end < 67u && job.title[end])
		end++;
	for (i = 0; i < 68u; i++)
		WORK[0xC0 + i] = i < end ? job.title[i] : 0;
	WORK[6] = (u8)job.title_break; /* second line starts here */
	WORK[7] = 0;
}

/* Advances the current job by at most one card command; call once per frame. */
void mc_tick(void)
{
	if (busy())
		return;
#ifdef MC_TEST_CUT
	if (issued >= MC_TEST_CUT)
		return; /* TEST: the power goes after MC_TEST_CUT card commands */
#endif
	mc_log[1]++;
	switch (job.state) {
	case ST_INFO:
		if (job.pos == 0) {
			job.pos = 1;
			issue(((fn5)MC_GETINFO)(0, 0, (s32)&job.type, (s32)&job.free, (s32)&job.format));
			return;
		}
		/* result 0: same card, -1: a new formatted card; type 2 = PS2 card; format 1 = formatted */
		if ((job.result != 0 && job.result != -1) || job.type != 2 || job.format != 1) {
			fail();
			return;
		}
		/* room for the new copy (the old file stays until the swap) and the folder with its icons */
		if ((u32)job.free < (job.size + 1023u) / 1024u + (ICON_SIZE + ICON_SYS_SIZE) / 1024u + 8u) {
			job.result = -1000;
			fail();
			return;
		}
		job.state = ST_MKDIR;
		job.pos = 0;
		return;
	case ST_MKDIR:
		if (job.pos == 0) {
			job.pos = 1;
			issue(((fn3)MC_MKDIR)(0, 0, (s32)job.dir));
			return;
		}
		job.pos = 0;
		if (job.result == 0)
			job.state = ST_ISYS_OPEN; /* new folder: icons first */
		else if (job.result == -4)
			job.state = ST_DEL_TMP; /* exists */
		else
			fail();
		return;
	case ST_ISYS_OPEN:
	case ST_ICO_OPEN:
		if (job.pos == 0) {
			job.pos = 1;
			issue(mc_open(job.state == ST_ISYS_OPEN ? job.isys : job.ico, MC_WRONLY | MC_CREAT));
			return;
		}
		if (job.result < 0) {
			fail();
			return;
		}
		job.fd = (u32)job.result;
		job.pos = 0;
		job.state++;
		return;
	case ST_ISYS_WRITE:
	case ST_ICO_WRITE: {
		const u32 n = job.state == ST_ISYS_WRITE ? ICON_SYS_SIZE : ICON_SIZE;
		if (job.pos == 0) {
			job.pos = 1;
			if (job.state == ST_ISYS_WRITE)
				icon_sys();
			issue(((fn3)MC_WRITE)((s32)job.fd, job.state == ST_ISYS_WRITE ? (s32)WORK : (s32)ICON_DATA, (s32)n));
			return;
		}
		if (job.result != (s32)n) {
			fail();
			return;
		}
		job.pos = 0;
		job.state++;
		return;
	}
	case ST_ISYS_CLOSE:
	case ST_ICO_CLOSE:
	case ST_CLOSE:
	case ST_VCLOSE:
	case ST_LCLOSE:
		if (job.pos == 0) {
			job.pos = 1;
			issue(((fn3)MC_CLOSE)((s32)job.fd, 0, 0));
			return;
		}
		job.pos = 0;
		if (job.result != 0) {
			fail();
			return;
		}
		if (job.state == ST_LCLOSE)
			job.state = ST_DONE;
		else if (job.state == ST_ICO_CLOSE)
			job.state = ST_DEL_TMP;
		else
			job.state++;
		return;
	case ST_DEL_TMP:
	case ST_DEL_OLD:
		if (job.pos == 0) {
			job.pos = 1;
			issue(((fn3)MC_DELETE)(0, 0, (s32)(job.state == ST_DEL_TMP ? job.tmp : job.path)));
			return;
		}
		job.pos = 0;
		if (job.result != 0 && job.result != -4) { /* -4: no such file */
			fail();
			return;
		}
		job.state++;
		return;
	case ST_OPEN_TMP:
	case ST_VOPEN:
		if (job.pos == 0) {
			job.pos = 1;
			issue(mc_open(job.tmp, job.state == ST_OPEN_TMP ? MC_WRONLY | MC_CREAT : MC_RDONLY));
			return;
		}
		if (job.result < 0) {
			fail();
			return;
		}
		job.fd = (u32)job.result;
		job.pos = 0;
		job.max = 0; /* offset */
		job.state++;
		return;
	case ST_WRITE:
	case ST_VREAD: {
		const u32 n = job.size - job.max < CHUNK ? job.size - job.max : CHUNK;
		if (job.pos == 0) {
			if (n == 0) {
				job.state++;
				return;
			}
			job.pos = 1;
			if (job.state == ST_WRITE) {
				mc_log[2]++;
				issue(((fn3)MC_WRITE)((s32)job.fd, (s32)(job.src + job.max), (s32)n));
			} else {
				issue(((fn3)MC_READ)((s32)job.fd, (s32)WORK, (s32)n));
			}
			return;
		}
		job.pos = 0;
		if (job.result != (s32)n) {
			fail();
			return;
		}
		if (job.state == ST_VREAD) {
			u32 i;
			mc_log[3]++;
			for (i = 0; i < n; i++)
				if (WORK[i] != job.src[job.max + i]) {
					job.result = -1001; /* read back differs */
					fail();
					return;
				}
		}
		job.max += n;
		return;
	}
	case ST_RENAME:
		if (job.pos == 0) {
			job.pos = 1;
			issue(((fn4)MC_RENAME)(0, 0, (s32)job.tmp, (s32)job.name));
			return;
		}
		if (job.result != 0) {
			fail();
			return;
		}
		job.state = ST_DONE;
		return;
	case ST_DIR:
		if (job.pos == 0) {
			job.pos = 1;
			issue(((s32(*)(s32, s32, s32, s32, s32, s32))MC_GETDIR)(0, 0, (s32)job.path, 0, (s32)job.max, (s32)job.dst));
			return;
		}
		if (job.result < 0) {
			if (job.result == -4) { /* nothing matches */
				job.size = 0;
				job.state = ST_DONE;
				return;
			}
			fail();
			return;
		}
		job.size = (u32)job.result;
		job.state = ST_DONE;
		return;
	case ST_LOPEN:
	case ST_LOPEN_TMP:
		if (job.pos == 0) {
			job.pos = 1;
			issue(mc_open(job.state == ST_LOPEN ? job.path : job.tmp, MC_RDONLY));
			return;
		}
		job.pos = 0;
		if (job.result < 0) {
			if (job.state == ST_LOPEN && job.result == -4) {
				job.state = ST_LOPEN_TMP; /* a save cut between delete and rename */
				return;
			}
			fail();
			return;
		}
		job.fd = (u32)job.result;
		job.state = ST_LREAD;
		return;
	case ST_LREAD: {
		const u32 n = job.max - job.size < CHUNK ? job.max - job.size : CHUNK;
		if (job.pos == 0) {
			if (n == 0) {
				job.state = ST_LCLOSE;
				return;
			}
			job.pos = 1;
			issue(((fn3)MC_READ)((s32)job.fd, (s32)(job.dst + job.size), (s32)n));
			return;
		}
		job.pos = 0;
		if (job.result < 0) {
			fail();
			return;
		}
		job.size += (u32)job.result;
		if ((u32)job.result < n)
			job.state = ST_LCLOSE; /* end of file */
		return;
	}
	default:
		return;
	}
}
