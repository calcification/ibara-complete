-- mame ibarablk ... -autoboot_script bl_bullet_count.lua (env OUT, BOSS type): per frame "frame bullets all boss_parts stage". PS2: run_stage.py --define BL_BCOUNT.
-- per frame: frame, enemy bullets alive (pool 0C297B40, can-hit flag), boss parts alive (type BOSS), stage byte
local m = manager.machine; local sp = m.devices[":maincpu"].spaces["program"]
local ports = m.ioport.ports; local function fld(p, n) return ports[p].fields[n] end
local P1 = 0x0C29D1D8; local frame = 0; local plan = {}
local function at(f, fn) plan[f] = plan[f] or {}; table.insert(plan[f], fn) end
local function press(f, p, n, len) at(f, function() fld(p, n):set_value(1) end); at(f + (len or 6), function() fld(p, n):clear_value() end) end
local t0 = 2400
press(t0, ":PORT_C", "Coin 1", 8); press(t0 + 60, ":PORT_C", "1 Player Start", 8)
for i = 0, 8 do press(t0 + 300 + i * 40, ":PORT_D", "P1 Button 1", 6) end
at(t0 + 700, function() fld(":PORT_D", "P1 Button 1"):set_value(1) end)
local out = io.open(os.getenv("OUT"), "w"); local BOSS = tonumber(os.getenv("BOSS") or "5")
emu.register_frame_done(function()
  frame = frame + 1
  if plan[frame] then for _, fn in ipairs(plan[frame]) do fn() end end
  if frame <= t0 + 700 then return end
  sp:write_u8(P1 + 0x288, 240); sp:write_u32(0x0C297A3C, 0x800000); sp:write_u8(P1 + 0x25B, 2)
  local f = frame - t0 - 700
  local b, all = 0, 0
  for i = 0, 255 do local fl = sp:read_u32(0x0C297B40 + i * 0x54); if (fl & 0x10004000) == 0x10000000 then b = b + 1 end; if (fl & 0x80000000) ~= 0 then all = all + 1 end end
  local bp = 0
  for i = 0, 191 do local a = 0x0C286578 + i * 0xB4; if (sp:read_u32(a) & 0x80000000) ~= 0 and sp:read_u32(a + 4) == BOSS then bp = bp + 1 end end
  out:write(string.format("%d %d %d %d %d\n", f, b, all, bp, sp:read_u8(0x0C3C4170)))
  if f == 14000 then out:close(); m:exit() end
end)
