-- mame ibarablk -rompath ROMS -video none -sound none -nothrottle -nodrc -autoboot_script bl_rank_bomb.lua
-- env OUT, MODE=none|bomb|hadou, B (bomb frame after takeoff, default 1200), RANK (hex, default 600000),
-- AUTO=1 (pick up items: P1 follows nothing; items are collected only by flying into them, so roses are left).
-- Stage 1, P1 straight A, invincible, shot held, 3 bombs. Rank is held at RANK until B-1, then free. Every write to
-- BL's stored rank 0C297A3C is logged with frame (relative to B), writer PC, caller PR, delta and new value.
-- research/phase24.
local m = manager.machine; local cpu = m.devices[":maincpu"]; local sp = cpu.spaces["program"]
local ports = m.ioport.ports; local function fld(p, n) return ports[p].fields[n] end
local P1 = 0x0C29D1D8; local frame, f = 0, -100000; local plan = {}
local function at(fr, fn) plan[fr] = plan[fr] or {}; table.insert(plan[fr], fn) end
local function press(fr, p, n, len) at(fr, function() fld(p, n):set_value(1) end); at(fr + (len or 6), function() fld(p, n):clear_value() end) end
local t0 = 2400
press(t0, ":PORT_C", "Coin 1", 8); press(t0 + 60, ":PORT_C", "1 Player Start", 8)
for i = 0, 8 do press(t0 + 300 + i * 40, ":PORT_D", "P1 Button 1", 6) end
if os.getenv("NOSHOT") ~= "1" then at(t0 + 700, function() fld(":PORT_D", "P1 Button 1"):set_value(1) end) end
local MODE = os.getenv("MODE") or "none"; local B = tonumber(os.getenv("B") or "1200")
local RANK = tonumber(os.getenv("RANK") or "600000", 16); local END = tonumber(os.getenv("END") or "600")
local out = io.open(assert(os.getenv("OUT")), "w")
local function bullets() local b = 0; for i = 0, 255 do if (sp:read_u32(0x0C297B40 + i * 0x54) & 0x10004000) == 0x10000000 then b = b + 1 end end return b end
TAP = sp:install_write_tap(0x0C297A38, 0x0C297A3F, "rank", function(offset, data, mask)
  if (mask & 0xFFFFFFFF) ~= 0xFFFFFFFF or f < 0 then return end
  local old, new = sp:read_u32(0x0C297A3C), data & 0xFFFFFFFF
  if new == old then return end
  out:write(string.format("W f=%d pc=%08X pr=%08X d=%d new=%06X\n", f, cpu.state["PC"].value, cpu.state["PR"].value, new - old, new))
end)
emu.register_frame_done(function()
  frame = frame + 1
  if plan[frame] then for _, fn in ipairs(plan[frame]) do fn() end end
  if frame <= t0 + 700 then return end
  f = frame - t0 - 700 - B
  sp:write_u8(P1 + 0x288, 240)
  if f < 0 then sp:write_u32(0x0C297A3C, RANK); sp:write_u8(P1 + 0x25D, 3); return end
  if f == 0 then out:write(string.format("B mode=%s rank=%06X bullets=%d bombs=%d\n", MODE, sp:read_u32(0x0C297A3C), bullets(), sp:read_u8(P1 + 0x25D))) end
  if MODE == "bomb" then
    if f == 0 then fld(":PORT_D", "P1 Button 2"):set_value(1) end
    if f == 6 then fld(":PORT_D", "P1 Button 2"):clear_value() end
  elseif MODE == "hadou" then
    if f == 0 then fld(":PORT_D", "P1 Button 2"):set_value(1) end
    if f == 140 then fld(":PORT_D", "P1 Button 2"):clear_value() end
  end
  if f % 20 == 0 then
    local it = {}
    for i = 0, 127 do local a = 0x0C3BC7CC + i * 0x60; if (sp:read_u32(a) & 0x80000000) ~= 0 then local k = sp:read_u32(a + 4) .. "/" .. sp:read_u32(a + 8); it[k] = (it[k] or 0) + 1 end end
    local s = ""; for k, n in pairs(it) do s = s .. k .. "x" .. n .. " " end
    out:write(string.format("S f=%d rank=%06X bullets=%d bombs=%d items[%s]\n", f, sp:read_u32(0x0C297A3C), bullets(), sp:read_u8(P1 + 0x25D), s))
  end
  if f == END then out:close(); m:exit() end
end)
