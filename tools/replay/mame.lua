-- MAME 0.276, ibarablk main set. Keep ROM, NVRAM, recordings and traces local.
local machine = manager.machine
local ports = machine.ioport.ports
local memory = machine.devices[":maincpu"].spaces["program"]
local replay = os.getenv("REPLAY_MODE") == "playback"
local start = assert(tonumber(os.getenv("REPLAY_START")), "REPLAY_START is required")
local xtc_address = tonumber(os.getenv("REPLAY_XTC_ADDRESS"))
local xtc_divisor = tonumber(os.getenv("REPLAY_XTC_DIVISOR")) or 1
local rng_address = tonumber(os.getenv("REPLAY_RNG_ADDRESS"))
local plan = {}
for line in io.lines(assert(os.getenv("REPLAY_PLAN"))) do
    local mask = assert(tonumber(line), "invalid plan row")
    assert(mask >= 0 and mask <= 1023, "unmapped MAME control")
    table.insert(plan, mask)
end
assert(#plan > 0 and start > 1 and start % 1 == 0, "invalid run start or plan")
local output = assert(io.open(assert(os.getenv("REPLAY_OUT")), "w"))
output:write("frame,observed_input,player_x,player_y,score,rank,hostile_bullets,enemies,enemy_type,enemy_state,enemy_hp,stage,bomb_stock,lives,xtc,rng\n")
local bindings = {
    {":PORT_D", 0x01}, {":PORT_D", 0x02}, {":PORT_D", 0x04}, {":PORT_D", 0x08},
    {":PORT_D", 0x10}, {":PORT_D", 0x20}, {":PORT_D", 0x40}, {":PORT_D", 0x80},
    {":PORT_C", 0x10}, {":PORT_C", 0x04},
}
for _, binding in ipairs(bindings) do
    local port = assert(ports[binding[1]], "wrong MAME machine")
    binding.port = port
    for _, field in pairs(port.fields) do
        if field.mask == binding[2] then binding.field = field end
    end
    assert(binding.field, "input field missing")
end

local function set_inputs(mask)
    for index, binding in ipairs(bindings) do
        if mask & (1 << (index - 1)) ~= 0 then
            binding.field:set_value(1)
        else
            binding.field:clear_value()
        end
    end
end

local function observed_inputs()
    local mask = 0
    for index, binding in ipairs(bindings) do
        if binding.port:read() & binding[2] == 0 then
            mask = mask | (1 << (index - 1))
        end
    end
    return mask
end

local function sample(frame)
    local stage = memory:read_u8(0x0C3C4170)
    if frame == 0 then assert(stage == 2, "frame zero did not reach stage 1") end
    local visible, bullets = 0, 0
    local enemy_type, enemy_state, enemy_hp = "", "", ""
    for i = 0, 191 do
        local slot = 0x0C286578 + i * 0xB4
        if memory:read_u32(slot) & 0x80000000 ~= 0 then
            visible = visible + 1
            if enemy_type == "" then
                enemy_type = memory:read_u32(slot + 4)
                enemy_state = memory:read_u32(slot + 8)
                enemy_hp = memory:read_u16(slot + 0x3C)
            end
        end
    end
    for i = 0, 255 do
        local slot = 0x0C297B40 + i * 0x54
        if memory:read_u32(slot) & 0x10004000 == 0x10000000 then bullets = bullets + 1 end
    end
    local player = 0x0C29D1D8
    if frame == 0 and os.getenv("REPLAY_REQUIRE_BULLETS") == "1" then
        assert(bullets > 0 and memory:read_u8(player + 0x25D) > 0,
               "cancellation checkpoint needs active hostile bullets and a bomb")
    end
    output:write(table.concat({
        frame, observed_inputs(), memory:read_i32(player + 0x10) // 65536,
        memory:read_i32(player + 0x14) // 65536,
        memory:read_u32(0x0C29D468), memory:read_u32(0x0C297A3C),
        bullets, visible, enemy_type, enemy_state, enemy_hp, stage,
        memory:read_u8(player + 0x25D), memory:read_u8(player + 0x25A),
        xtc_address and memory:read_u32(xtc_address) // xtc_divisor or "",
        rng_address and memory:read_u32(rng_address) or "",
    }, ","), "\n")
end

local function bootstrap_mask(frame)
    if frame >= 2401 and frame < 2409 then return 512 end
    if frame >= 2461 and frame < 2469 then return 256 end
    if frame >= 2701 and frame < 3027 and (frame - 2701) % 40 < 6 then return 16 end
    return 0
end

local clock = 0
emu.register_frame_done(function()
    clock = clock + 1
    local frame = clock - start
    if frame >= 0 and frame < #plan then sample(frame) end
    if frame == #plan - 1 then
        output:close()
        machine:exit()
        return
    end
    if not replay then
        local next_frame = frame + 1
        set_inputs(next_frame >= 0 and plan[next_frame + 1] or bootstrap_mask(clock + 1))
    end
end)
