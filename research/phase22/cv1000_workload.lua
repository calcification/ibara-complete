-- MAME 0.276, Ibara. Read-only measurement of the EP1C12 on the emulated board.
-- The caller holds the returned object and calls take_frame once per VBlank.

local M = {}
local RAM_START = 0x0c000000
local RAM_END = 0x0c800000
local SUBMIT = 0x18000004
local GAME_LIST = 0x0c392dd8
local GAME_CLIP_X = 0x0c21cc30
local GAME_CLIP_Y = 0x0c26c8c8

local function axis_blocks(origin, length)
    local offset, tail = origin & 31, length % 32
    local blocks = (length // 32) * (offset == 0 and 1 or 2)
    if tail ~= 0 then
        blocks = blocks + (offset + tail > 32 and 2 or 1)
    end
    return blocks
end

M.list_fields = {
    "draws", "visible_draws", "blended_draws", "clipped_pixels",
    "source_vram_blocks", "dest_vram_blocks", "upload_bytes", "list_bytes",
}

function M.inspect_list(read_word, start, clip_x, clip_y)
    local totals = {}
    for _, name in ipairs(M.list_fields) do totals[name] = 0 end
    local pos = start
    local screen_clip = true
    local finish = math.min(RAM_END, start + 0x200000)
    while pos >= RAM_START and pos + 2 <= finish do
        local command = read_word(pos)
        local op = command >> 12
        if op == 0 or op == 15 then
            totals.list_bytes = pos + 2 - start
            return totals
        end
        if op == 12 and pos + 4 <= finish then
            screen_clip = read_word(pos + 2) ~= 0
            pos = pos + 4
        elseif op == 2 and pos + 16 <= finish then
            local width = (read_word(pos + 12) & 0x1fff) + 1
            local height = (read_word(pos + 14) & 0x0fff) + 1
            local bytes = 16 + width * height * 2
            totals.upload_bytes = totals.upload_bytes + bytes
            pos = pos + bytes
        elseif op == 1 and pos + 20 <= finish then
            local sx, sy = read_word(pos + 4), read_word(pos + 6)
            local x, y = read_word(pos + 8), read_word(pos + 10)
            local width = (read_word(pos + 12) & 0x1fff) + 1
            local height = (read_word(pos + 14) & 0x0fff) + 1
            local right, bottom = (x + width - 1) & 0xffff, (y + height - 1) & 0xffff
            if screen_clip then
                x, y = math.max(x, clip_x - 32), math.max(y, clip_y - 32)
                right = math.min(right, clip_x + 319 + 32)
                bottom = math.min(bottom, clip_y + 239 + 32)
            else
                right, bottom = math.min(right, 8191), math.min(bottom, 4095)
            end
            totals.draws = totals.draws + 1
            if right >= x and bottom >= y then
                local w, h = right - x + 1, bottom - y + 1
                totals.visible_draws = totals.visible_draws + 1
                totals.blended_draws = totals.blended_draws + ((command & 0x0200) ~= 0 and 1 or 0)
                totals.clipped_pixels = totals.clipped_pixels + w * h
                totals.source_vram_blocks = totals.source_vram_blocks + axis_blocks(sx, w) * axis_blocks(sy, h)
                totals.dest_vram_blocks = totals.dest_vram_blocks + axis_blocks(x, w) * axis_blocks(y, h)
            end
            pos = pos + 20
        else
            return nil, string.format("unexpected blitter command %04x at %08x", command, pos)
        end
    end
    return nil, "blitter list exceeded RAM or the capture size"
end

-- Read only after the game has published the current frame's list.
function M.read_list(space)
    local start = space:read_u32(GAME_LIST) & 0x1fffffff
    return M.inspect_list(function(addr) return space:read_u16(addr) end, start,
        space:read_i32(GAME_CLIP_X), space:read_i32(GAME_CLIP_Y))
end

function M.attach(machine)
    local space = machine.devices[":maincpu"].spaces["program"]
    local delay
    for name, index in pairs(machine.devices[":blitter"].items) do
        if name:match("/m_blit_delay_ns$") then delay = emu.item(index) end
    end
    local capture = {enabled = false, frame = {}}
    local function record_modeled_delay(job)
        if job and delay and not job.modeled_ns then job.modeled_ns = delay:read(0) end
    end
    capture.tap = space:install_write_tap(SUBMIT & ~7, SUBMIT | 7, "workload-submit", function(_, data, mask)
        if capture.enabled and (data & mask & 1) ~= 0 then
            record_modeled_delay(capture.frame[#capture.frame])
            -- The retail submit routine reads this pointer immediately before kicking the FPGA.
            local totals, message = M.read_list(space)
            capture.frame[#capture.frame + 1] = {list = totals, error = message}
        end
    end)
    function capture:take_frame()
        local jobs = self.frame
        record_modeled_delay(jobs[#jobs])
        self.frame = {}
        return jobs
    end
    return capture
end

return M
