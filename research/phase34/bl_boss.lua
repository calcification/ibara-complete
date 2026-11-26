-- Resume a naturally reached stage checkpoint and record one boss HP source.
local machine = manager.machine
local space = machine.devices[":maincpu"].spaces.program
local function required(name)
  local value = assert(os.getenv(name), "set " .. name)
  return value
end

local checkpoint = required("RESUME_STATE")
local stage = assert(tonumber(required("STAGE")))
local seed = assert(tonumber(required("SEED")))
local target = assert(tonumber(required("BOSSTYPE")))
local gauge = tonumber(os.getenv("GAUGE_HP") or "")
local stop = tonumber(os.getenv("MAXFRAMES") or "18000")
local held = machine.ioport.ports[":PORT_D"].fields["P1 Button 1"]
local output = required("OUT")
local temporary = output .. ".partial"
local out = assert(io.open(temporary, "w"))
local frame, resumed, started = 0, 0, false
local seen = {}

local function finish(why)
  out:write("# ", why, "\n")
  out:close()
  assert(os.rename(temporary, output))
  machine:exit()
end

emu.register_frame_done(function()
  frame = frame + 1
  if frame == 1 then
    held:set_value(1)
    machine:load(checkpoint)
    return
  end
  local active_stage = space:read_u8(0x0C3C4170)
  if not started then
    if active_stage ~= stage then
      if frame > 120 then finish("checkpoint did not reach the requested stage") end
      return
    end
    space:write_u32(0x0C207578, seed)
    out:write(string.format("# stage %d seed %d\n", stage - 1, seed))
    started = true
  end
  if active_stage ~= stage then finish("stage ended"); return end
  if resumed >= stop then finish("sample limit"); return end
  space:write_u8(0x0C29D460, 240)
  space:write_u32(0x0C297A3C, 0x800000)
  space:write_u8(0x0C29D433, 2)
  if resumed % 4 == 0 then
    for slot = 0, 191 do
      local part = 0x0C286578 + 0xB4 * slot
      if space:read_u32(part) & 0x80000000 ~= 0 then
        local kind, subtype = space:read_u32(part + 4), space:read_u32(part + 8)
        local hp = space:read_u16(part + 0x3C)
        if target == 0 then
          local value = space:read_u32(part + 0x40)
          local id = string.format("%d/%d", kind, subtype)
          if value >= 50000 and not seen[id] then
            out:write(string.format("# candidate %d %d %d %d %d %d\n", resumed, slot, kind, subtype, hp, value))
            seen[id] = true
          end
        elseif kind == target and subtype == 0 then
          if gauge then hp = space:read_u32(gauge) end
          out:write(string.format("%d %d %d 00000000\n", resumed, slot, hp))
          if hp > 0 then seen[slot] = true end
          if hp == 0 and seen[slot] then finish("observed zero HP"); return end
        end
      end
    end
  end
  resumed = resumed + 1
end)
