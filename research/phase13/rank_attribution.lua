-- log writes to BL's stored rank 0C297A3C (0 hardest .. 2^24 easiest): writer PC, delta histogram
local m = manager.machine; local cpu = m.devices[":maincpu"]; local sp = cpu.spaces["program"]
local ports = m.ioport.ports; local function fld(p, n) return ports[p].fields[n] end
local stats, frame, last = {}, 0, nil
local pending = {}          -- rank writes this frame: {pr, delta}
local prev_streak = nil
local kinds = {"smallP","option","fragment","medal","largeP","fullbomb","1UP","score"}
local function streak() local t = {} for k = 0, 7 do t[k] = sp:read_u8(0x0C22E2AC + k) end return t end
local attrib = {}
RANK_TAP = sp:install_write_tap(0x0C297A38, 0x0C297A3F, "rank", function(offset, data, mask)
  if (mask & 0xFFFFFFFF) ~= 0xFFFFFFFF then return end   -- rank = low 32 bits (big-endian +4)
  local old = sp:read_u32(0x0C297A3C)
  local new = data & 0xFFFFFFFF
  local pc = string.format("%08X", cpu.state["PC"].value)
  local d = (new - old)
  local pr = string.format("%08X", cpu.state["PR"].value)
  local k = pc .. " PR " .. pr .. " " .. tostring(d)
  stats[k] = (stats[k] or 0) + 1
  table.insert(pending, {pr, d})
end)
local plan = {}
local function at(f, fn) plan[f] = plan[f] or {}; table.insert(plan[f], fn) end
local function press(f, p, n, len) at(f, function() fld(p, n):set_value(1) end); at(f + (len or 6), function() fld(p, n):clear_value() end) end
local t0 = 2400
press(t0, ":PORT_C", "Coin 1", 8); press(t0 + 60, ":PORT_C", "1 Player Start", 8)
for i = 0, 8 do press(t0 + 300 + i * 40, ":PORT_D", "P1 Button 1", 6) end
at(t0 + 700, function() fld(":PORT_D", "P1 Button 1"):set_value(1) end)
for i = 0, 40 do press(t0 + 900 + i * 300, ":PORT_D", (i % 2 == 0) and "P1 Left" or "P1 Right", 90) end
for i = 0, 6 do press(t0 + 1500 + i * 1500, ":PORT_D", "P1 Button 2", 8) end  -- bombs
emu.register_frame_done(function()
  frame = frame + 1
  if plan[frame] then for _, fn in ipairs(plan[frame]) do fn() end end
  local now = streak()
  if prev_streak and #pending > 0 then
    local changed = {}
    for k = 0, 7 do if now[k] > prev_streak[k] then table.insert(changed, kinds[k + 1]) end end
    local who = (#changed > 0) and table.concat(changed, "+") or "none"
    for _, w in ipairs(pending) do local key = w[1] .. " " .. tostring(w[2]) .. " <- " .. who; attrib[key] = (attrib[key] or 0) + 1 end
  end
  pending = {}; prev_streak = now
  if frame % 1200 == 0 then print(string.format("FRAME %d rank=%06X score=%d lives=%d bombs=%d", frame, sp:read_u32(0x0C297A3C), sp:read_u32(0x0C29D468), sp:read_u8(0x0C29D1D8+0x25A), sp:read_u8(0x0C29D1D8+0x25D))) end
  if frame == t0 + 12000 then
    local l = {} for k, v in pairs(stats) do l[#l + 1] = {k, v} end
    table.sort(l, function(a, b) return a[2] > b[2] end)
    for i = 1, math.min(#l, 60) do print("W", l[i][1], l[i][2]) end
    for k, v in pairs(attrib) do print("A", k, v) end
    m:exit()
  end
end)
