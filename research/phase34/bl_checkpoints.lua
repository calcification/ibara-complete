-- Checkpoint stationary P1 after natural stage entry, once per stage.
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
local ticks = {}
for value in (os.getenv("CHECKPOINT_TICKS") or "1000,1000,1000,1000,1000"):gmatch("[^,]+") do
  ticks[#ticks + 1] = assert(tonumber(value))
end
local last_stage = tonumber(os.getenv("LAST_STAGE") or "5")
assert(last_stage and last_stage >= 1 and last_stage <= 5 and #ticks >= last_stage)
local directory = assert(os.getenv("OUTDIR"), "set OUTDIR")
local files = {}
for stage = 1, last_stage do
  assert(ticks[stage] >= 0 and ticks[stage] % 1 == 0, "checkpoint ticks must be nonnegative integers")
  local path = directory .. "/stage-" .. stage .. ".sta"
  local existing = io.open(path, "rb")
  if existing then
    existing:close()
    error("use a fresh checkpoint directory")
  end
  files[stage] = path
end
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
  if stage < 2 or stage > last_stage + 1 then return end
  start[stage] = start[stage] or frame
  local tick = frame - start[stage]
  if tick == ticks[stage - 1] then
    local file = files[stage - 1]
    m:save(file)
    print("Stage checkpoint", stage - 1, frame, file); io.stdout:flush()
  end
  if stage == last_stage + 1 and tick > ticks[last_stage] then
    local saved = io.open(files[last_stage], "rb")
    if saved then saved:close(); m:exit() end
  end
end)
