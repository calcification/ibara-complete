-- research/phase28 (graze sound volume): mame ibarablk -autoboot_script bl_sound_log.lua (env OUT).
-- BL: stage 1, invincible, shot held; per frame, YMZ770 channels that are playing: channel, phrase, volume, volume2, pan
local m = manager.machine; local sp = m.devices[":maincpu"].spaces["program"]
local ports = m.ioport.ports; local function fld(p, n) return ports[p].fields[n] end
local P1 = 0x0C29D1D8; local frame = 0; local plan = {}
local function at(f, fn) plan[f] = plan[f] or {}; table.insert(plan[f], fn) end
local function press(f, p, n, len) at(f, function() fld(p, n):set_value(1) end); at(f + (len or 6), function() fld(p, n):clear_value() end) end
local t0 = 2400
press(t0, ":PORT_C", "Coin 1", 8); press(t0 + 60, ":PORT_C", "1 Player Start", 8)
for i = 0, 8 do press(t0 + 300 + i * 40, ":PORT_D", "P1 Button 1", 6) end
at(t0 + 700, function() fld(":PORT_D", "P1 Button 1"):set_value(1) end)
local dev = m.devices[":ymz770"]
local ph = emu.item(dev.items["0/m_channels.phrase"]); local pl = emu.item(dev.items["0/m_channels.is_playing"])
local vo = emu.item(dev.items["0/m_channels.volume"]); local v2 = emu.item(dev.items["0/m_channels.volume2"])
local pa = emu.item(dev.items["0/m_channels.pan"])
local out = io.open(os.getenv("OUT"), "w")
emu.register_frame_done(function()
  frame = frame + 1
  if plan[frame] then for _, fn in ipairs(plan[frame]) do fn() end end
  if frame <= t0 + 700 then return end
  sp:write_u8(P1 + 0x288, 240)
  local s = {}
  for c = 0, 15 do if pl:read(c) ~= 0 then s[#s + 1] = string.format("%d:%d:%d:%d:%d", c, ph:read(c), vo:read(c), v2:read(c), pa:read(c)) end end
  out:write(frame - t0, " ", sp:read_u32(P1 + 0x280), " ", table.concat(s, " "), "\n")
  if frame > t0 + 700 + 7000 then out:close(); m:exit() end
end)
