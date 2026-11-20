local m = manager.machine; local sp = m.devices[":maincpu"].spaces["program"]; local f = 0
emu.register_frame_done(function()
  f = f + 1; if f ~= 120 then return end
  local out = io.open(os.getenv("PATOUT"), "w")
  for s = 0, 7 do
    local lt = sp:read_u32(0x0C17F388 + 4 * s)
    for l = 0, 6 do
      local p = sp:read_u32(lt + 4 * l); local n = sp:read_u32(p)
      local t = {}
      for i = 0, n * 6 do t[#t + 1] = string.format("%08X", sp:read_u32(p + 4 * i)) end
      out:write(string.format("%d %d %s\n", s, l, table.concat(t, " ")))
    end
  end
  out:close(); m:exit()
end)
