-- research/phase43: input lag A/B. mame ibarablk -autoboot_script mame_lag_ab.lua (env ST = savestate, OUT, PRESS=0|1, DIR). Load ST with shot held; with PRESS=1 hold DIR from the frame after frame T; hash the screen each frame. The first frame whose hash differs between PRESS=0 and PRESS=1 is when the input became visible.
local m = manager.machine; local ports = m.ioport.ports
local function f(n) return ports[":PORT_D"].fields[n] end
local scr = m.screens[":screen"]
local frame, T = 0, 30
local out = io.open(os.getenv("OUT"), "w")
emu.register_frame_done(function()
  frame = frame + 1
  if frame == 1 then f("P1 Button 1"):set_value(1); m:load(os.getenv("ST")); return end
  local k = frame - 1
  if k == T and os.getenv("PRESS") == "1" then f(os.getenv("DIR") or "P1 Right"):set_value(1) end
  if k >= T - 2 and k <= T + 12 then
    local px = scr:pixels()
    local h = 0
    for i = 1, #px, 97 do h = (h * 31 + px:byte(i)) % 4294967291 end
    out:write(string.format("%d %d\n", k - T, h))
  end
  if k > T + 12 then out:close(); m:exit() end
end)
