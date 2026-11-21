-- mame ibarablk -rompath ROMS -video none -sound none -nothrottle -autoboot_script bl_pod_rate.lua -skip_gameinfo  (OUT=file)
-- Output: "w pool type n" new shots and "A w pool type n" alive-shot frames per weapon (weapon ids 0 rocket .. 6 5way).
-- PS2 counterpart: run_stage.py --stage 1 --shot-level 2 --define BL_RATE_TEST --define BL_TEST_ALL_WEAPONS (0x01FE0000 / 0x01FE0200).
-- BL pod fire rate per weapon: invincible, rank locked, shot held, all weapons owned; weapon change (Button 4)
-- every 1200 frames; new shots counted per (weapon, pool, type) over frames 200..1199 of each segment.
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
local alive = {}; local cnt = {}
local START = 2400
emu.register_frame_done(function()
  frame = frame + 1
  if plan[frame] then for _, fn in ipairs(plan[frame]) do fn() end end
  if frame <= t0 + 700 then return end
  sp:write_u8(P1 + 0x288, 240); sp:write_u32(0x0C297A3C, 0x800000); sp:write_u8(P1 + 0x25B, tonumber(os.getenv("SHOT") or "2"))
  local f = frame - t0 - 700
  if f == START - 100 then for k = 0, 6 do sp:write_u32(0x0C22E028 + 4 * k, 1) end end
  if f >= START then
    local seg = (f - START) % 1200
    if seg == 0 then fld(":PORT_D", "P1 Button 4"):set_value(1) end
    if seg == 8 then fld(":PORT_D", "P1 Button 4"):clear_value() end
    local w = sp:read_u8(P1 + 0x26F)
    for pi, pool in ipairs({{0x0C2380D0, 160}, {0x0C2A6D9C, 64}}) do
      for k = 0, pool[2] - 1 do
        local a = pool[1] + 0x34 * k; local key = pi * 1000 + k
        local on = (sp:read_u32(a) >> 30) == 3
        if on and not alive[key] and seg >= 200 then
          local id = string.format("%d %d %d", w, pi, sp:read_u32(a + 4) & 0xFF)
          cnt[id] = (cnt[id] or 0) + 1
        end
        if on and seg >= 200 then
          local id = string.format("A %d %d %d", w, pi, sp:read_u32(a + 4) & 0xFF)
          cnt[id] = (cnt[id] or 0) + 1
        end
        alive[key] = on
      end
    end
  end
  if f == START + 1200 * 8 then
    for id, n in pairs(cnt) do out:write(id .. " " .. n .. "\n") end
    out:close(); m:exit()
  end
end)
