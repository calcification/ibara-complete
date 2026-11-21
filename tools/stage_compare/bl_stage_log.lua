-- Black Label (MAME ibarablk) stage logger for the PS2 comparison. Study tool; reads/writes only emulated RAM.
--
-- mame ibarablk -rompath ROMS -video none -sound none -nothrottle -autoboot_script bl_stage_log.lua -skip_gameinfo
--
-- Environment:
--   OUTDIR    directory for spawns.txt, bullets.txt, core.txt (required)
--   STAGE     BL stage byte to log: 2 = stage 1 ... 7 = stage 6 (default 2)
--   RANKLOCK  stored rank to hold every frame (e.g. 8388608 = 0x800000); unset = free rank
--   SHOTLOCK  shot level to hold every frame; unset = free
--   NOSHOT=1  untouched boss: parts of type BOSSTYPE keep their first-seen HP every frame while STAGE is logged
--             (same rule as the PS2 logger's BL_NOSHOT; the player keeps shooting)
--   MAXFRAMES frames after the game starts before exiting (default 60000); also exits when STAGE ends
-- The player is kept invincible (BL +0x288). Output formats (frames count from the first spawn of STAGE):
--   spawns.txt  frame stage slot type subtype hp score x y segment
--   bullets.txt frame slot type x0 y0 dx dy   (px/frame averaged over the first 6 frames)
--   core.txt    frame slot hp subtype x y mode step  (parts of type BOSSTYPE (default 5) with subtype < 3 or
--               score >= 50000, every 4 frames; mode = +0x9A, step = +0xA6)
--   tables.txt  type table index score hp     (each part-record table seen at +0x10: 128 entries of 16 bytes,
--               score at +4, base HP at +0xE)
local m = manager.machine; local sp = m.devices[":maincpu"].spaces["program"]
local ports = m.ioport.ports; local function fld(p, n) return ports[p].fields[n] end
local P1, EN, BUL, RANK, STAGEB = 0x0C29D1D8, 0x0C286578, 0x0C297B40, 0x0C297A3C, 0x0C3C4170
local dir = assert(os.getenv("OUTDIR"), "set OUTDIR")
local STAGE = tonumber(os.getenv("STAGE") or "2")
local BOSST = tonumber(os.getenv("BOSSTYPE") or "5")
local MAXF = tonumber(os.getenv("MAXFRAMES") or "60000")
local out = io.open(dir .. "/spawns.txt", "w"); local bout = io.open(dir .. "/bullets.txt", "w")
local cout = io.open(dir .. "/core.txt", "w")
local tout = io.open(dir .. "/tables.txt", "w"); local tseen = {}
local frame, first, shooting, left = 0, nil, false, false
local alive, typ, balive, bpend, hp0 = {}, {}, {}, {}, {}
local NOSHOT = os.getenv("NOSHOT")
local plan = {}
local function at(f, fn) plan[f] = plan[f] or {}; table.insert(plan[f], fn) end
local function press(f, p, n, len) at(f, function() fld(p, n):set_value(1) end); at(f + (len or 6), function() fld(p, n):clear_value() end) end
local t0 = 2400
press(t0, ":PORT_C", "Coin 1", 8); press(t0 + 60, ":PORT_C", "1 Player Start", 8)
for i = 0, 8 do press(t0 + 300 + i * 40, ":PORT_D", "P1 Button 1", 6) end
at(t0 + 700, function() fld(":PORT_D", "P1 Button 1"):set_value(1); shooting = true end)
local sout = os.getenv("SHOTS") and io.open(dir .. "/shots.txt", "w"); local salive = {}; local sframe = 0
local function shot_frame()  -- every new player shot (pool 0C2380D0, 160 x 0x34): frame slot type +8 +C
  sframe = sframe + 1
  local c0, c2 = 0, 0   -- per-frame alive counts (both BL pools): line "frame 255 count0 count2 0"
  for k = 0, 159 do
    local a = 0x0C2380D0 + 0x34 * k
    if (sp:read_u32(a) >> 30) == 3 then if (sp:read_u32(a + 4) & 0xFF) == 2 then c2 = c2 + 1 elseif (sp:read_u32(a + 4) & 0xFF) == 0 then c0 = c0 + 1 end end
  end
  for k = 0, 63 do
    local a = 0x0C2A6D9C + 0x34 * k
    if (sp:read_u32(a) >> 30) == 3 then if (sp:read_u32(a + 4) & 0xFF) == 0 then c0 = c0 + 1 end end
  end
  sout:write(string.format("%d 255 %d %d 0\n", sframe, c0, c2))
  for k = 0, 159 do
    local a = 0x0C2380D0 + 0x34 * k
    local on = (sp:read_u32(a) >> 30) == 3
    if on and not salive[k] then
      sout:write(string.format("%d %d %d %d %d\n", sframe, k, sp:read_u32(a + 4) & 0xFF, sp:read_u32(a + 8) & 0xFF, sp:read_u32(a + 12) & 0xFF))
    end
    salive[k] = on
  end
end
local function finish() if sout then sout:close() end; out:close(); bout:close(); cout:close(); tout:close(); m:exit() end
emu.register_frame_done(function()
  frame = frame + 1
  if plan[frame] then for _, fn in ipairs(plan[frame]) do fn() end end
  if frame <= t0 + 700 then return end
  if sout and sframe < 30000 then shot_frame() end
  sp:write_u8(P1 + 0x288, 240)
  if os.getenv("RANKLOCK") then sp:write_u32(RANK, tonumber(os.getenv("RANKLOCK"))) end
  if os.getenv("SHOTLOCK") then sp:write_u8(P1 + 0x25B, tonumber(os.getenv("SHOTLOCK"))) end
  local stage = sp:read_u8(STAGEB)
  if stage > STAGE and first then left = true end
  if left or frame > t0 + 700 + MAXF then finish(); return end
  if stage ~= STAGE then return end
  for i = 0, 191 do
    local a = EN + i * 0xB4
    local fl = sp:read_u32(a); local on = (fl & 0x80000000) ~= 0
    local t = sp:read_u32(a + 4)
    if on and (not alive[i] or typ[i] ~= t) then
      first = first or frame
      out:write(string.format("%d %d %d %d %08X %d %d %d %d %d\n", frame - first, stage, i, t, sp:read_u32(a + 8),
        sp:read_u16(a + 0x3C), sp:read_u32(a + 0x40), sp:read_u32(a + 0x24) >> 16, sp:read_u32(a + 0x28) >> 16, (fl >> 14) & 1))
      local tb = sp:read_u32(a + 0x10); local key = t .. ":" .. tb
      if not tseen[key] then
        tseen[key] = true
        for k = 0, 127 do
          tout:write(string.format("%d %08X %d %d %d\n", t, tb, k, sp:read_u32(tb + 16 * k + 4), sp:read_i16(tb + 16 * k + 14)))
        end
      end
    end
    if on and (not alive[i] or typ[i] ~= t) then hp0[i] = sp:read_u16(a + 0x3C) end
    if NOSHOT and on and t == BOSST and hp0[i] and hp0[i] > 0 then sp:write_u16(a + 0x3C, hp0[i]) end
    alive[i] = on; typ[i] = t
    if on and t == BOSST and first and (frame - first) % (os.getenv("EVERY") and 1 or 4) == 0 and (sp:read_u32(a + 8) < 3 or sp:read_u32(a + 0x40) >= 50000) then
      cout:write(string.format("%d %d %d %08X %d %d %d %d\n", frame - first, i, sp:read_u16(a + 0x3C), sp:read_u32(a + 8),
        sp:read_u32(a + 0x24) >> 16, sp:read_u32(a + 0x28) >> 16, sp:read_u8(a + 0x9A), sp:read_u8(a + (os.getenv("HIT") and 0x84 or 0xA6))))
    end
  end
  if not first then return end
  for i = 0, 255 do
    local a = BUL + i * 0x54
    local on = (sp:read_u32(a) & 0x10004000) == 0x10000000
    local p = bpend[i]
    if p then
      p.age = p.age + 1
      if not on then bpend[i] = nil
      elseif p.age == 6 then
        local x = sp:read_u32(a + 0x28); local y = sp:read_u32(a + 0x2C)
        local dx = ((x - p.x0 + 0x80000000) % 0x100000000 - 0x80000000) / 65536 / 6
        local dy = ((y - p.y0 + 0x80000000) % 0x100000000 - 0x80000000) / 65536 / 6
        bout:write(string.format("%d %d %d %d %d %.3f %.3f\n", p.f, i, p.t, p.x0 >> 16, p.y0 >> 16, dx, dy))
        bpend[i] = nil
      end
    end
    if on and not balive[i] then
      bpend[i] = {f = frame - first, t = sp:read_u32(a + 4), x0 = sp:read_u32(a + 0x28), y0 = sp:read_u32(a + 0x2C), age = 0}
    end
    balive[i] = on
  end
end)
