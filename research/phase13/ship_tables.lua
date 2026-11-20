local m = manager.machine; local sp = m.devices[":maincpu"].spaces["program"]; local f = 0
emu.register_frame_done(function()
  f = f + 1; if f ~= 120 then return end
  local function words(name, a, n) local t = {} for i = 0, n - 1 do t[#t + 1] = string.format("%08X", sp:read_u32(a + 4 * i)) end print(name, table.concat(t, " ")) end
  words("SHOTFN_0C17E1FC", 0x0C17E1FC, 16)
  words("SHIPREC_0C17E12C", 0x0C17E12C, 32)
  words("T_0C174FF0", 0x0C174FF0, 4)
  words("T_0C17F388", 0x0C17F388, 16)
  words("T_0C182834", 0x0C182834, 2)
  words("T_0C1740D0", 0x0C1740D0, 16)
  m:exit()
end)
