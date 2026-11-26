local m = manager.machine
local sp = m.devices[":maincpu"].spaces.program
local ports = m.ioport.ports
local plan = {}
local function press(f, port, name, length)
  local field = ports[port].fields[name]
  plan[f] = function() field:set_value(1) end
  if length then plan[f + length] = function() field:clear_value() end end
end
press(2400, ":PORT_C", "Coin 1", 8)
press(2460, ":PORT_C", "1 Player Start", 8)
for i=0,8 do press(2700 + i * 40, ":PORT_D", "P1 Button 1", 6) end
press(3100, ":PORT_D", "P1 Button 1")
local frame = 0
local start = {}
emu.register_frame_done(function()
  frame = frame + 1
  if plan[frame] then plan[frame]() end
  if frame <= 3100 then return end
  sp:write_u8(0x0C29D460, 240)
  sp:write_u32(0x0C297A3C, 0x800000)
  sp:write_u8(0x0C29D433, 2)
  local stage = sp:read_u8(0x0C3C4170)
  if stage < 2 or stage > 6 then return end
  start[stage] = start[stage] or frame
  if frame - start[stage] == 1000 then
    local file = assert(os.getenv("OUTDIR")) .. "/stage-" .. (stage - 1) .. ".sta"
    m:save(file)
    print("Stage checkpoint", stage - 1, frame, file); io.stdout:flush()
  end
  if stage == 6 and frame - start[6] == 1003 then m:exit() end
end)
