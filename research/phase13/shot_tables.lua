local m = manager.machine; local sp = m.devices[":maincpu"].spaces["program"]; local f = 0
emu.register_frame_done(function()
  f = f + 1; if f ~= 120 then return end
  local function words(a, n) local t = {} for i = 0, n - 1 do t[#t + 1] = string.format("%08X", sp:read_u32(a + 4 * i)) end return table.concat(t, " ") end
  for s = 0, 7 do
    local p = sp:read_u32(0x0C17F388 + 4 * s)
    print(string.format("SHIP%d %08X levels: %s", s, p, words(p, 7)))
  end
  local lv0 = sp:read_u32(sp:read_u32(0x0C17F388))      -- straight A, level 0
  local lv0s = sp:read_u32(sp:read_u32(0x0C17F388 + 16)) -- spread A, level 0
  print(string.format("PAT straightA L0 @%08X: %s", lv0, words(lv0, 12)))
  print(string.format("PAT spreadA   L0 @%08X: %s", lv0s, words(lv0s, 12)))
  m:exit()
end)
