-- BL rank glow capture (research/phase28): per level 8..15 (rank so that h = 16 L + 8), alpha +0x274 forced to 0xC0,
-- pods (+0x289) forced on; 32 logged frames per level: "G frame level fc px py buf" then the glow draw ops.
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
local function w16(a) return sp:read_u16(a) end
local level, dumpnow = nil, false
local function draws(base)
  local a = base; local list = {}
  for n = 1, 4000 do
    local op = w16(a); local t = op & 0xF000
    if t == 0x1000 then
      local f = {}; for k = 0, 9 do f[#f + 1] = w16(a + 2 * k) end
      if f[2] == 0xC0C0 and f[3] >= 0x1500 and f[3] < 0x1600 and f[4] >= 0x700 and f[4] < 0x800 then
        local s = {}; for k = 1, 10 do s[k] = string.format("%x", f[k]) end; list[#list + 1] = table.concat(s, ",")
      end
      a = a + 20
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
      out:write(string.format("G %d %d %d %08X %08X %X %d\n", frame - t0, level or -1, sp:read_u32(0x0C2B039C),
        sp:read_u32(P1 + 0x10), sp:read_u32(P1 + 0x14), b, #l))
      for _, e in ipairs(l) do out:write("D " .. e .. "\n") end
    end
  end end)
local START = 1400
emu.register_frame_done(function()
  frame = frame + 1
  if plan[frame] then for _, fn in ipairs(plan[frame]) do fn() end end
  if frame <= t0 + 700 then return end
  sp:write_u8(P1 + 0x288, 240)
  local k = frame - t0 - START
  if k >= 0 then
    local L = 8 + (k // 48)
    if L > 15 then out:close(); m:exit(); return end
    level = L
    local h = 16 * L + 8
    sp:write_u32(0x0C297A3C, 0xFFFFFF - (h << 16))
    sp:write_u32(P1 + 0x274, 0xC0)
    sp:write_u8(P1 + 0x289, 3)
    if k % 48 >= 16 then dumpnow = true end
  end
end)
