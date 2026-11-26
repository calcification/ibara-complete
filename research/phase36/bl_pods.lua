-- MAME 0.276 interpreter. Resume Stage 2 at its 1,000-frame checkpoint.
local machine = manager.machine
local cpu = machine.devices[":maincpu"]
local space = cpu.spaces.program
local ports = machine.ioport.ports
local p1, pool, stage = 0x0C29D1D8, 0x0C2380D0, 0x0C3C4170
local shot, change = ports[":PORT_D"].fields["P1 Button 1"], ports[":PORT_D"].fields["P1 Button 4"]
local weapon, seed = tonumber(os.getenv("WEAPON")), tonumber(os.getenv("SEED"))
local kind = assert(({[3]=4, [4]=7, [6]=2})[weapon], "choose weapon 3, 4, or 6")
local state, path = assert(os.getenv("RESUME_STATE")), assert(os.getenv("OUT"))
local frame, tick, exposure, exact, sampled, occupied = 0, 0, 0, 0, 0, 0
local started, busy = false, false
local tap, reads
local attempts, x, y, ship = 0, 0, 0, 0
local caller = ({[3]=0x0C07893C, [4]=0x0C077D9C, [6]=0x0C078338})[weapon]
local last, writers = {}, {}
local empty = os.getenv("POD_EMPTY") == "1"
local start, stop = 1500, 2500 -- elapsed from the loaded state

local function lane(value, shift)
  if math.type(value) == "float" then
    if value >= 2.0 ^ 64 then return 0xFFFFFFFF end
    return math.floor(value / 2.0 ^ shift) % 0x100000000
  end
  return (value >> shift) & 0xFFFFFFFF
end

local function track(offset, data, mask)
  if busy or tick < start or tick >= stop then return end
  local address = offset + ((pool - offset) % 4)
  if (address - pool) % 52 ~= 0 then address = address + 4 end
  local delta = address - pool
  local shift = (4 - (address - offset)) * 8
  if delta < 0 or delta >= 48 * 52 or delta % 52 ~= 0 or shift < 0
     or lane(mask, shift) ~= 0xFFFFFFFF or lane(data, shift) >> 30 ~= 3 then return end
  busy = true
  if space:read_u32(address) == 0 then
    exact = exact + 1
    local pc = cpu.state.PC.value
    writers[pc] = (writers[pc] or 0) + 1
  end
  busy = false
end

local function probe_attempt()
  if busy or tick < start or tick >= stop then return end
  local pc = cpu.state.PC.value
  if (pc == 0x0C0718F8 or pc == 0x0C0718FA)
     and cpu.state.PR.value == caller and cpu.state.R3.value == 0 then
    attempts = attempts + 1
  end
end

emu.register_frame_done(function()
  frame = frame + 1
  if frame == 1 then
    shot:set_value(1)
    machine:load(state)
    return
  end
  if space:read_u8(stage) ~= 3 then
    if started or frame > 120 then error("expected Stage 2 throughout the exposure") end
    return
  end
  if not started then
    for index = 0, 6 do space:write_u32(0x0C22E028 + 4 * index, 1) end
    started = true
  end
  space:write_u8(p1 + 0x288, 240)
  space:write_u32(0x0C297A3C, 0x800000)
  space:write_u8(p1 + 0x25B, 2)
  if tick < 800 and tick % 20 == 0 and space:read_u8(p1 + 0x26F) ~= weapon then change:set_value(1) end
  if tick % 20 == 6 then change:clear_value() end
  if tick == 1000 then space:write_u32(0x0C207578, seed) end
  if empty and tick >= 200 and tick < stop then
    for slot = 0, 191 do space:write_u32(0x0C286578 + 0xB4 * slot, 0) end
  end

  if tick >= start - 1 and tick < stop then
    assert(space:read_u8(p1 + 0x26F) == weapon, "weapon changed")
    for index = 0, 2 do
      assert(space:read_u8(p1 + 0x26C + index) == 2 * weapon, "pod kind does not match weapon")
    end
    if tick == start then
      x, y = space:read_i32(p1 + 0x10) // 65536, space:read_i32(p1 + 0x14) // 65536
      ship = space:read_u32(p1 + 4)
    end
    busy = true
    for index = 0, 47 do
      local address = pool + 52 * index
      local on = space:read_u32(address) >> 30 == 3 and (space:read_u32(address + 4) & 0xFF) == kind
      if on and tick >= start then
        occupied = occupied + 1
        if not last[index] then sampled = sampled + 1 end
      end
      last[index] = on
    end
    busy = false
    if tick >= start then exposure = exposure + 1 end
  end
  if tick == start - 1 then
    -- frame-done runs after the CPU. The tap observes the following update.
    local lo, hi = pool & ~7, (pool + 48 * 52 - 1) | 7
    tap = space:install_write_tap(lo, hi, "pod-allocation", track)
    reads = space:install_read_tap(lo, hi, "pod-allocation-attempt", probe_attempt)
  elseif tick == stop - 1 then
    reads:remove()
    tap:remove()
    local out = assert(io.open(path, "w"))
    out:write(string.format("%d %d %d %d %d %d %d %d %d %d\n",
      weapon, seed, exposure, exact, sampled, occupied, attempts, x, y, ship))
    for pc, count in pairs(writers) do out:write(string.format("%08X %d\n", pc, count)) end
    out:close()
    machine:exit()
  end
  tick = tick + 1
end)
