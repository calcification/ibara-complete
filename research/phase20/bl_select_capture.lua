-- mame ibarablk -nodrc -autoboot_script bl_select_capture.lua (env OUT): one-player select screen run; logs every
-- frame's element draw ops in game coordinates (background tiles and frame-buffer copies left out):
-- F frame count, then attr,alpha,srcx,srcy,x,y,w,h,tintr,tintgb. research/phase20.
-- full select-screen capture: element ops per frame (game coords), background excluded
local m = manager.machine; local sp = m.devices[":maincpu"].spaces["program"]
local ports = m.ioport.ports; local function fld(p, n) return ports[p].fields[n] end
local frame = 0; local plan = {}
local function at(f, fn) plan[f] = plan[f] or {}; table.insert(plan[f], fn) end
local function press(f, p, n, len) at(f, function() fld(p, n):set_value(1) end); at(f + (len or 6), function() fld(p, n):clear_value() end) end
local t0 = 2400
press(t0, ":PORT_C", "Coin 1", 8); press(t0 + 20, ":PORT_C", "Coin 1", 8); press(t0 + 60, ":PORT_C", "1 Player Start", 8)
press(t0 + 205, ":PORT_D", "P1 Right", 6)
press(t0 + 300, ":PORT_D", "P1 Left", 6)
press(t0 + 400, ":PORT_D", "P1 Button 1", 6)
press(t0 + 460, ":PORT_D", "P1 Down", 6)
press(t0 + 510, ":PORT_D", "P1 Down", 6)
press(t0 + 560, ":PORT_D", "P1 Down", 6)
press(t0 + 610, ":PORT_D", "P1 Down", 6)
press(t0 + 660, ":PORT_D", "P1 Up", 6)
press(t0 + 720, ":PORT_D", "P1 Button 1", 6)
SHOTS = {350, 450, 480, 530, 580, 630, 690, 730, 760, 800, 860, 950}
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
  if frame == t0 + 1000 then out:close(); m:exit() end
end)
