-- mame ibarablk -nodrc -autoboot_script bl_graze_log.lua (env OUT): one player, stage 1, invincible, shot held from
-- +700; per frame "P frame px py <player +0x270..+0x28F hex>"; on blitter exec, the draw list (D lines as
-- research/phase20/bl_blitter_log.lua) for up to 400 frames where +0x270 / +0x284 are non-zero and 60 where they are
-- zero. research/phase21 (BL's XTC graze visuals, 0C071110).
local m = manager.machine; local sp = m.devices[":maincpu"].spaces["program"]
local ports = m.ioport.ports; local function fld(p, n) return ports[p].fields[n] end
local P1 = 0x0C29D1D8; local frame = 0; local plan = {}
local function at(f, fn) plan[f] = plan[f] or {}; table.insert(plan[f], fn) end
local function press(f, p, n, len) at(f, function() fld(p, n):set_value(1) end); at(f + (len or 6), function() fld(p, n):clear_value() end) end
local t0 = 2400
press(t0, ":PORT_C", "Coin 1", 8); press(t0 + 60, ":PORT_C", "1 Player Start", 8)
for i = 0, 8 do press(t0 + 300 + i * 40, ":PORT_D", "P1 Button 1", 6) end
at(t0 + 700, function() fld(":PORT_D", "P1 Button 1"):set_value(1) end)
local out = io.open(os.getenv("OUT"), "w")
local active, idle, dumpnow = 0, 0, false
local function w16(a) return sp:read_u16(a) end
local function draws(base)
  local a = base; local list = {}
  for n = 1, 4000 do
    local op = w16(a); local t = op & 0xF000
    if t == 0x1000 then local f = {}; for k = 0, 9 do f[#f + 1] = string.format("%x", w16(a + 2 * k)) end; list[#list + 1] = table.concat(f, ","); a = a + 20
    elseif t == 0xC000 then a = a + 4
    elseif t == 0x2000 then a = a + 16 + ((w16(a + 12) & 0x1fff) + 1) * ((w16(a + 14) & 0xfff) + 1) * 2
    else break end
  end
  return list
end
T = sp:install_write_tap(0x18000000, 0x18000007, "ex", function(o, d, mask)
  if (d & mask & 1) == 1 and dumpnow then
    dumpnow = false
    for _, b in ipairs({0x0C3CC400, 0x0C46C500}) do
      local l = draws(b)
      out:write(string.format("F %d %X %d\n", frame - t0, b, #l)); for _, e in ipairs(l) do out:write("D " .. e .. "\n") end
    end
  end end)
emu.register_frame_done(function()
  frame = frame + 1
  if plan[frame] then for _, fn in ipairs(plan[frame]) do fn() end end
  if frame <= t0 + 700 then return end
  sp:write_u8(P1 + 0x288, 240)
  local s = string.format("P %d %08X %08X", frame - t0, sp:read_u32(P1 + 0x10), sp:read_u32(P1 + 0x14))
  for o = 0x270, 0x28C, 4 do s = s .. string.format(" %08X", sp:read_u32(P1 + o)) end
  out:write(s .. "\n")
  local on = sp:read_u8(P1 + 0x270) ~= 0 or sp:read_u16(P1 + 0x284) ~= 0
  if on and active < 400 then active = active + 1; dumpnow = true
  elseif not on and idle < 60 and frame % 7 == 0 then idle = idle + 1; dumpnow = true end
  if frame - t0 > 7000 then out:close(); m:exit() end
end)
