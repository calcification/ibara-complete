local m = manager.machine; local sp = m.devices[":maincpu"].spaces["program"]; local f = 0
emu.register_frame_done(function()
  f = f + 1; if f ~= 120 then return end
  for a = 0x0C160000, 0x0C1E0000, 4 do
    if sp:read_u32(a) == 0x0C07E5C0 then
      local t = {} for i = -4, 11 do t[#t + 1] = string.format("%08X", sp:read_u32(a + 4 * i)) end
      print(string.format("TABLE near %08X: %s", a, table.concat(t, " ")))
    end
  end
  m:exit()
end)
