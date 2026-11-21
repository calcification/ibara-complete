-- mame ibarablk -nodrc -autoboot_script bl_blitter_log.lua (env OUT): coin, start, the ship select (Right at +205,
-- P2 Start at +260). On every blitter exec: each upload op (U dx dy w h ram-address frame first-64-bytes) and,
-- from +64, each new draw list (F frame buffer count, then D attr,alpha,srcx,srcy,dstx,dsty,w-1,h-1,tintr,tintgb).
-- Job lists: 0C3CC400 / 0C46C500 (double-buffered). research/phase20.
local m = manager.machine; local sp = m.devices[":maincpu"].spaces["program"]
local ports = m.ioport.ports; local function fld(p, n) return ports[p].fields[n] end
local frame = 0; local plan = {}
local function at(f, fn) plan[f] = plan[f] or {}; table.insert(plan[f], fn) end
local function press(f, p, n, len) at(f, function() fld(p, n):set_value(1) end); at(f + (len or 6), function() fld(p, n):clear_value() end) end
local t0 = 2400
press(t0, ":PORT_C", "Coin 1", 8); press(t0 + 20, ":PORT_C", "Coin 1", 8); press(t0 + 60, ":PORT_C", "1 Player Start", 8)
press(t0 + 205, ":PORT_D", "P1 Right", 6); press(t0 + 260, ":PORT_C", "2 Players Start", 8)
local out = io.open(os.getenv("OUT"), "w"); local seen = {}
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
local function scan(base)
  local a = base
  for n = 1, 4000 do
    local op = w16(a); local t = op & 0xF000
    if t == 0x1000 then a = a + 20
    elseif t == 0xC000 then a = a + 4
    elseif t == 0x2000 then
      local dx, dy, dimx, dimy = w16(a + 8) & 0x1fff, w16(a + 10) & 0xfff, (w16(a + 12) & 0x1fff) + 1, (w16(a + 14) & 0xfff) + 1
      local key = string.format("%d,%d,%d,%d", dx, dy, dimx, dimy)
      local head = sp:read_range(a + 16, a + 16 + 63, 8)
      local k2 = key .. head
      if not seen[k2] then seen[k2] = 1; out:write(string.format("U %d %d %d %d %08X %d %s\n", dx, dy, dimx, dimy, a + 16, frame, (head:gsub(".", function(c) return string.format("%02x", c:byte()) end)))) ; out:flush() end
      a = a + 16 + dimx * dimy * 2
    else break end
  end
end
T = sp:install_write_tap(0x18000000, 0x18000007, "ex", function(o, d, mask)
  if (d & mask & 1) == 1 and frame >= t0 + 64 then
    for _, b in ipairs({0x0C3CC400, 0x0C46C500}) do
      local l = draws(b); local key = table.concat(l, ";")
      if #l > 0 and not seen[key] then seen[key] = 1; out:write(string.format("F %d %X %d\n", frame - t0, b, #l)); for _, e in ipairs(l) do out:write("D " .. e .. "\n") end end
    end
  end end)
emu.register_frame_done(function()
  frame = frame + 1
  if plan[frame] then for _, fn in ipairs(plan[frame]) do fn() end end
  if frame == t0 + 330 then out:close(); m:exit() end
end)
