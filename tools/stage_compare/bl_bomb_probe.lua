-- mame ibarablk -rompath ROMS -video none -sound none -nothrottle -autoboot_script bl_bomb_probe.lua (env OUT, SHIPVARIANT=A|B, BOMBS, FRAGS, SHOT):
-- P1 bomb at frame 700 after start; per frame: player-shot pool 0C229004 records by type/subtype and enemy bullets. research/phase18.
-- BL bomb probe: straight A (or SHIPVARIANT=B spread), bombs set, Button 2 pressed at BOMBAT; per frame dump
local m = manager.machine; local sp = m.devices[":maincpu"].spaces["program"]
local ports = m.ioport.ports; local function fld(p, n) return ports[p].fields[n] end
local P1 = 0x0C29D1D8; local frame = 0; local plan = {}
local function at(f, fn) plan[f] = plan[f] or {}; table.insert(plan[f], fn) end
local function press(f, p, n, len) at(f, function() fld(p, n):set_value(1) end); at(f + (len or 6), function() fld(p, n):clear_value() end) end
local t0 = 2400
press(t0, ":PORT_C", "Coin 1", 8); press(t0 + 60, ":PORT_C", "1 Player Start", 8)
if os.getenv("SHIPVARIANT") == "B" then press(t0 + 250, ":PORT_D", "P1 Right", 6) end
for i = 0, 8 do press(t0 + 300 + i * 40, ":PORT_D", "P1 Button 1", 6) end
local out = io.open(os.getenv("OUT"), "w")
local BOMBS = tonumber(os.getenv("BOMBS") or "3"); local FRAGS = tonumber(os.getenv("FRAGS") or "0")
local SHOT = tonumber(os.getenv("SHOT") or "1")
local B = 700; local prev = nil
emu.register_frame_done(function()
  frame = frame + 1
  if plan[frame] then for _, fn in ipairs(plan[frame]) do fn() end end
  if frame <= t0 + 700 then return end
  local f = frame - t0 - 700
  sp:write_u32(0x0C297A3C, 0x800000)
  sp:write_u8(P1 + 0x288, 240); if f < B then sp:write_u8(P1 + 0x25D, BOMBS); sp:write_u8(P1 + 0x25E, FRAGS); sp:write_u8(P1 + 0x25B, SHOT) end
  if f == B then fld(":PORT_D", "P1 Button 2"):set_value(1) end
  if f == B + 6 then fld(":PORT_D", "P1 Button 2"):clear_value() end
  if f >= B - 2 and f < B + 400 then
    local rec = {}
    for o = 0x200, 0x29F do rec[#rec + 1] = sp:read_u8(P1 + o) end
    local d = ""
    if prev then for i, v in ipairs(rec) do if v ~= prev[i] then d = d .. string.format("%X:%02X>%02X ", 0x1FF + i, prev[i], v) end end end
    prev = rec
    local c = {}
    for k = 0, 127 do local a = 0x0C229004 + 0x50 * k; if (sp:read_u32(a) & 0x80000000) ~= 0 then local t = string.format("%d/%d", sp:read_u32(a + 4), sp:read_u32(a + 8)); c[t] = (c[t] or 0) + 1 end end
    local cs = ""; for t, n in pairs(c) do cs = cs .. t .. "x" .. n .. " " end
    local b = 0; for i = 0, 255 do local fl = sp:read_u32(0x0C297B40 + i * 0x54); if (fl & 0x10004000) == 0x10000000 then b = b + 1 end end
    cs = cs .. "| bullets " .. b
    out:write(string.format("%d inv=%d bombs=%d frags=%d shots[%s] %s\n", f - B, sp:read_u8(P1 + 0x288), sp:read_u8(P1 + 0x25D), sp:read_u8(P1 + 0x25E), cs, ""))
  end
  if f == B + 400 then out:close(); m:exit() end
end)
