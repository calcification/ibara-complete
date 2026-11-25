-- research/phase20 stage two: player 2 starts alone (2P Start), player 1 side shows the join panel (env OUT); make_select_data.py --long
-- research/phase20 stage two: player 2 (joins at 120) holds each state 240 frames (env OUT, KIND=S|P); make_select_data.py --long
-- mame ibarablk -nodrc -autoboot_script bl_select_capture_p2.lua (env OUT, VARIANT=S|P): two-player select screen
-- run for research/phase20/make_select_data.py --p2. Player 2 starts at frame 120 and then makes the same inputs at the
-- same frames as player 1 does in the one-player captures (VARIANT S ends on the straight ship, P on the spread ship).
-- Logs every frame's element draw ops as bl_select_capture.lua does. research/phase20.
local m = manager.machine; local sp = m.devices[":maincpu"].spaces["program"]
local ports = m.ioport.ports; local function fld(p, n) return ports[p].fields[n] end
local frame = 0; local plan = {}
local function at(f, fn) plan[f] = plan[f] or {}; table.insert(plan[f], fn) end
local function press(f, p, n, len) at(f, function() fld(p, n):set_value(1) end); at(f + (len or 6), function() fld(p, n):clear_value() end) end
local t0 = 2400
press(t0, ":PORT_C", "Coin 1", 8); press(t0 + 20, ":PORT_C", "Coin 1", 8); press(t0 + 60, ":PORT_C", "2 Players Start", 8)
local s0 = 300
local H = 240
SHOTS = {}
local out = io.open(os.getenv("OUT"), "w")
local function w16(a) return sp:read_u16(a) end
local function s16(v) if v >= 0x8000 then return v - 0x10000 end return v end
local last = ""
local function dump(base)
  local a = base; local list = {}; local org = nil
  for n = 1, 4000 do
    local op = w16(a); local t = op & 0xF000
    if t == 0x1000 then
      local f = {}; for k = 0, 9 do f[k] = w16(a + 2 * k) end
      local sx, sy, w, h = f[2] & 0x1fff, f[3] & 0xfff, (f[6] & 0x1fff) + 1, (f[7] & 0xfff) + 1
      if sx == 4256 and sy == 1792 then org = s16(f[4]) - 272 end
      if not (w == 32 and h == 32) and not (sx >= 960 and sx < 1320 and sy >= 136 and sy < 456) then list[#list + 1] = f end
      a = a + 20
    elseif t == 0xC000 then a = a + 4
    elseif t == 0x2000 then a = a + 16 + ((w16(a + 12) & 0x1fff) + 1) * ((w16(a + 14) & 0xfff) + 1) * 2
    else break end
  end
  return list, org
end
T = sp:install_write_tap(0x18000000, 0x18000007, "ex", function(o, d, mask)
  if (d & mask & 1) == 1 and frame >= t0 + 64 then
    for _, b in ipairs({0x0C3CC400, 0x0C46C500}) do
      local l, org = dump(b)
      if org then
        local s = {}
        for _, f in ipairs(l) do s[#s + 1] = string.format("%x,%x,%d,%d,%d,%d,%d,%d,%x,%x", f[0], f[1], f[2] & 0x1fff, f[3] & 0xfff, s16(f[4]) - org, s16(f[5]) - 136, (f[6] & 0x1fff) + 1, (f[7] & 0xfff) + 1, f[8], f[9]) end
        local key = table.concat(s, ";")
        if key ~= last then out:write(string.format("F %d %d\n%s\n", frame - t0, #s, table.concat(s, "\n"))); last = key end
      end
    end
  end end)
emu.register_frame_done(function()
  frame = frame + 1
  if plan[frame] then for _, fn in ipairs(plan[frame]) do fn() end end
  for _, k in ipairs(SHOTS) do if frame == t0 + k then m.video:snapshot() end end
  if frame == t0 + s0 + 8 * H then out:close(); m:exit() end
end)
