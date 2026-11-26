-- Stage 2 homing formation and target transitions. Use the Phase 36 checkpoint.
local m = manager.machine
local mem = m.devices[":maincpu"].spaces.program
local fields = m.ioport.ports[":PORT_D"].fields
local shot, change = fields["P1 Button 1"], fields["P1 Button 4"]
local directions = {"P1 Up", "P1 Down", "P1 Left", "P1 Right"}
local inputs = {0, 1, 5, 4, 6, 2, 10, 8, 9, 0}
local checkpoint = assert(os.getenv("RESUME_STATE"), "set RESUME_STATE")
local destination = assert(os.getenv("OUT"), "set OUT")
local clear_enemies = os.getenv("POD_EMPTY") == "1"
local player, pool = 0x0C29D1D8, 0x0C286578
local frame, tick, start = 0, 0, 1400
local last_mask
local out = assert(io.open(destination .. ".partial", "w"))
out:write("tick,mask,x,y,pod,angle,desired,target\n")

local function apply(mask)
  if mask == last_mask then return end
  for i, name in ipairs(directions) do
    local field = assert(fields[name])
    if mask & (1 << (i - 1)) ~= 0 then field:set_value(1) else field:clear_value() end
  end
  last_mask = mask
end

emu.register_frame_done(function()
  frame = frame + 1
  if frame == 1 then
    shot:set_value(1)
    m:load(checkpoint)
    return
  end
  if mem:read_u8(0x0C3C4170) ~= 3 then
    assert(tick == 0 and frame < 120, "expected the Stage 2 checkpoint")
    return
  end
  if tick == 0 then
    for i = 0, 6 do mem:write_u32(0x0C22E028 + 4 * i, 1) end
  end
  mem:write_u8(player + 0x288, 240)
  mem:write_u32(0x0C297A3C, 0x800000)
  mem:write_u8(player + 0x25B, 2)
  if tick < 800 and tick % 20 == 0 and mem:read_u8(player + 0x26F) ~= 3 then change:set_value(1) end
  if tick % 20 == 6 then change:clear_value() end
  if tick == 1000 then mem:write_u32(0x0C207578, 1) end
  if clear_enemies and tick >= 200 then
    for i = 0, 191 do mem:write_u32(pool + 0xB4 * i, 0) end
  end

  if tick >= start then
    assert(mem:read_u8(player + 0x26F) == 3, "expected homing")
    local pods = mem:read_u32(0x0C077B9C)
    local mask = mem:read_u16(player + 0x24C) & 15
    local x, y = mem:read_i32(player + 0x10), mem:read_i32(player + 0x14)
    for i = 0, 2 do
      assert(mem:read_u8(player + 0x26C + i) == 6, "expected a homing pod")
      local pod = pods + 48 * i
      out:write(string.format("%d,%d,%d,%d,%d,%d,%d,%d\n", tick - start, mask, x, y, i,
        mem:read_u16(pod + 36) & 511, mem:read_u16(pod + 38) & 511, mem:read_u16(pod + 40)))
    end
  end
  if tick >= start - 1 then apply(inputs[(tick + 1 - start) // 20 + 1] or 0) end
  if tick == start + 799 then
    out:close()
    assert(os.rename(destination .. ".partial", destination))
    m:exit()
  end
  tick = tick + 1
end)
