-- mame ibarablk -rompath ROMS -video none -sound none -nothrottle -nodrc -autoboot_script bl_cancel_log.lua (env OUT, END frames):
-- logs each write of 16 to BL's bullet-cancel counter 0C2B07FC (SET: frame, stage byte, PC) and every kill of a part
-- with score >= 1000 (KILL: HP > 0 -> 0, alive or freed). Invincible P1, held shot, rank locked. research/phase17.
local m = manager.machine; local sp = m.devices[":maincpu"].spaces["program"]
local ports = m.ioport.ports; local function fld(p, n) return ports[p].fields[n] end
local P1 = 0x0C29D1D8; local frame = 0; local plan = {}
local function at(f, fn) plan[f] = plan[f] or {}; table.insert(plan[f], fn) end
local function press(f, p, n, len) at(f, function() fld(p, n):set_value(1) end); at(f + (len or 6), function() fld(p, n):clear_value() end) end
local t0 = 2400
press(t0, ":PORT_C", "Coin 1", 8); press(t0 + 60, ":PORT_C", "1 Player Start", 8)
for i = 0, 8 do press(t0 + 300 + i * 40, ":PORT_D", "P1 Button 1", 6) end
at(t0 + 700, function() fld(":PORT_D", "P1 Button 1"):set_value(1) end)
local cpu = m.devices[":maincpu"]; SEEN = {}
local function sub33() local s = "" for i = 0, 191 do local a = 0x0C286578 + i * 0xB4; local ty = sp:read_u32(a + 4); if (sp:read_u32(a) & 0x80000000) ~= 0 and (ty == 33 or ty == 34 or ty == 11) then local k = ty * 65536 + sp:read_u32(a + 8); if not SEEN[k] then SEEN[k] = 1; s = s .. string.format("t%d/s%X/sc%d/hp%d ", ty, sp:read_u32(a + 8), sp:read_u32(a + 0x40), sp:read_u16(a + 0x3C)) end end end return s end
local out = io.open(os.getenv("OUT"), "w"); local f = 0
local function dying()
  local s = ""
  for i = 0, 191 do local a = 0x0C286578 + i * 0xB4; if (sp:read_u32(a) & 0x80000000) ~= 0 and sp:read_u16(a + 0x3C) == 0 and sp:read_u32(a + 0x40) >= 1000 then s = s .. string.format("t%d/s%X ", sp:read_u32(a + 4), sp:read_u32(a + 8)) end end
  return s
end
local function parts()
  local t = {}
  for i = 0, 191 do local a = 0x0C286578 + i * 0xB4; if (sp:read_u32(a) & 0x80000000) ~= 0 then local ty = sp:read_u32(a + 4); t[ty] = (t[ty] or 0) + 1 end end
  local s = ""; for k, n in pairs(t) do s = s .. k .. "x" .. n .. " " end; return s
end
CT = sp:install_write_tap(0x0C2B07F8, 0x0C2B07FF, "ct", function(offset, data, mask)
  local hi, lo = (data >> 32) & 0xFFFFFFFF, data & 0xFFFFFFFF; local mh, ml = (mask >> 32) & 0xFFFFFFFF, mask & 0xFFFFFFFF; if (mh ~= 0 and hi == 16) or (ml ~= 0 and lo == 16) then
    local regs = ""
    for r = 0, 14 do local v = cpu.state["R" .. r].value; if v >= 0x0C286578 and v < 0x0C286578 + 192 * 0xB4 then local i = (v - 0x0C286578) // 0xB4; local a = 0x0C286578 + i * 0xB4; if r == 5 or r == 8 then regs = regs .. string.format("R%d:t%d/s%X/sc%d ", r, sp:read_u32(a + 4), sp:read_u32(a + 8), sp:read_u32(a + 0x40)) end end end
    local line = string.format("SET f=%d st=%d pc=%08X pr=%08X %s| dying %s\n", f, sp:read_u8(0x0C3C4170), cpu.state["PC"].value, cpu.state["PR"].value, regs, dying()); local k = cpu.state["PC"].value .. regs; if k ~= LASTK or f - (LASTF or 0) > 30 then out:write(line); out:flush() end; LASTK = k; LASTF = f
  end
end)
emu.register_frame_done(function()
  frame = frame + 1
  if plan[frame] then for _, fn in ipairs(plan[frame]) do fn() end end
  if frame <= t0 + 700 then return end
  sp:write_u8(P1 + 0x288, 240); sp:write_u32(0x0C297A3C, 0x800000); sp:write_u8(P1 + 0x25B, 2)
  f = frame - t0 - 700
  HP = HP or {}
  for i = 0, 191 do local a = 0x0C286578 + i * 0xB4; local al = (sp:read_u32(a) & 0x80000000) ~= 0; local hp = sp:read_u16(a + 0x3C)
    if (HP[i] or 0) > 0 and hp == 0 and sp:read_u32(a + 0x40) >= 1000 then out:write(string.format("KILL f=%d st=%d t%d/s%X sc%d %s\n", f, sp:read_u8(0x0C3C4170), sp:read_u32(a + 4), sp:read_u32(a + 8), sp:read_u32(a + 0x40), al and "alive" or "freed")) end
    HP[i] = al and hp or 0 end
    if f == tonumber(os.getenv("END") or "30000") then out:close(); m:exit() end
end)
