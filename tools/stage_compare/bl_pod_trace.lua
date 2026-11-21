-- mame ibarablk ... -autoboot_script bl_pod_trace.lua  (env OUT, WEAPON 0..6, TYPE pod shot type): own all weapons, switch to
-- WEAPON, then from frame 3600 dump one pod-shot slot per frame (frame, +0x00..+0x30). PS2: run_stage.py --define
-- BL_TEST_ALL_WEAPONS --define BL_TRACE_WEAPON=w --define BL_TRACE_TYPE=t (0x01FD0000).
-- BL: frames of new pool-1 shots (frame type +8 +C x y) for WEAPON (env, default MG 5) over 2000 frames
local m = manager.machine; local sp = m.devices[":maincpu"].spaces["program"]
local ports = m.ioport.ports; local function fld(p, n) return ports[p].fields[n] end
local P1 = 0x0C29D1D8; local frame = 0; local plan = {}
local function at(f, fn) plan[f] = plan[f] or {}; table.insert(plan[f], fn) end
local function press(f, p, n, len) at(f, function() fld(p, n):set_value(1) end); at(f + (len or 6), function() fld(p, n):clear_value() end) end
local t0 = 2400
press(t0, ":PORT_C", "Coin 1", 8); press(t0 + 60, ":PORT_C", "1 Player Start", 8)
for i = 0, 8 do press(t0 + 300 + i * 40, ":PORT_D", "P1 Button 1", 6) end
at(t0 + 700, function() fld(":PORT_D", "P1 Button 1"):set_value(1) end)
local out = io.open(os.getenv("OUT"), "w"); local alive = {}
local tk, t0f, traced, seen = nil, 0, 0, {}
local TT = tonumber(os.getenv("TYPE") or "7")
local W = tonumber(os.getenv("WEAPON") or "5")
emu.register_frame_done(function()
  frame = frame + 1
  if plan[frame] then for _, fn in ipairs(plan[frame]) do fn() end end
  if frame <= t0 + 700 then return end
  sp:write_u8(P1 + 0x288, 240); sp:write_u32(0x0C297A3C, 0x800000); sp:write_u8(P1 + 0x25B, 2)
  local f = frame - t0 - 700
  if f == 2300 then for k = 0, 6 do sp:write_u32(0x0C22E028 + 4 * k, 1) end end
  if f >= 2350 and f < 2400 + 1200 and sp:read_u8(P1 + 0x26F) ~= W and f % 20 == 0 then fld(":PORT_D", "P1 Button 4"):set_value(1) end
  if f % 20 == 6 then fld(":PORT_D", "P1 Button 4"):clear_value() end
  if f >= 3600 and sp:read_u8(P1 + 0x26F) == W then
    if tk then
      local a = 0x0C2380D0 + 0x34 * tk
      if (sp:read_u32(a) >> 30) ~= 3 then out:write("END " .. f .. "\n"); traced = traced + 1; tk = nil
      else
        local s = string.format("%d", f - t0f)
        for o = 0, 0x30, 4 do s = s .. string.format(" %08X", sp:read_u32(a + o)) end
        out:write(s .. "\n")
      end
    elseif traced < 3 then
      for k = 0, 159 do
        local a = 0x0C2380D0 + 0x34 * k
        if (sp:read_u32(a) >> 30) == 3 and (sp:read_u32(a + 4) & 0xFF) == TT and not seen[k] then tk = k; t0f = f; break end
      end
    end
    for k = 0, 159 do seen[k] = (sp:read_u32(0x0C2380D0 + 0x34 * k) >> 30) == 3 end
  end
  if f == 5600 then out:close(); m:exit() end
end)
