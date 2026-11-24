-- mame ibarablk -rompath ROMS -video none -sound none -nothrottle -autoboot_script bl_scene_trace.lua (env OUT, MAXF)
-- Plays like tools/stage_compare/bl_stage_log.lua (invincible P1, shot held, rank 0x800000, shot level 2) and logs
-- every change of the stage byte (0C3C4170) and every jump of the stage-script pointer (0C2ABAA4) to another script
-- (a move other than 2..64 bytes forward), with the frame, the stage byte and the writer's PC/PR. research/phase25.
local m = manager.machine; local cpu = m.devices[":maincpu"]; local sp = cpu.spaces["program"]
local ports = m.ioport.ports; local function fld(p, n) return ports[p].fields[n] end
local P1, RANK, STAGEB, SPTR = 0x0C29D1D8, 0x0C297A3C, 0x0C3C4170, 0x0C2ABAA4
local MAXF = tonumber(os.getenv("MAXF") or "120000")
local out = io.open(assert(os.getenv("OUT")), "w")
local frame, last_stage, last_ptr = 0, -1, nil
local t0 = 2400
local plan = {}
local function at(f, fn) plan[f] = plan[f] or {}; table.insert(plan[f], fn) end
local function press(f, p, n, len) at(f, function() fld(p, n):set_value(1) end); at(f + (len or 6), function() fld(p, n):clear_value() end) end
press(t0, ":PORT_C", "Coin 1", 8); press(t0 + 60, ":PORT_C", "1 Player Start", 8)
for i = 0, 8 do press(t0 + 300 + i * 40, ":PORT_D", "P1 Button 1", 6) end
at(t0 + 700, function() fld(":PORT_D", "P1 Button 1"):set_value(1) end)
TAP = sp:install_write_tap(SPTR & ~7, SPTR | 7, "sptr", function(offset, data, mask)
  local v = data & 0xFFFFFFFF
  if (mask & 0xFFFFFFFF) ~= 0xFFFFFFFF then return end
  local old = sp:read_u32(SPTR)
  local d = v - old
  if d < 2 or d > 64 then
    out:write(string.format("JUMP f=%d stage=%d %08X -> %08X pc=%08X pr=%08X\n", frame, sp:read_u8(STAGEB), old, v,
      cpu.state["PC"].value, cpu.state["PR"].value))
  end
end)
local REC = 0x0C23E0A6  -- stage record id (index into the stage list 0C2065A0)
TAP2 = sp:install_write_tap(REC & ~7, REC | 7, "rec", function(offset, data, mask)
  local sh = (7 - (REC - offset)) * 8
  if ((mask >> sh) & 0xFF) == 0 then return end
  out:write(string.format("REC f=%d stage=%d %d -> %d pc=%08X pr=%08X\n", frame, sp:read_u8(STAGEB), sp:read_u8(REC),
    (data >> sh) & 0xFF, cpu.state["PC"].value, cpu.state["PR"].value))
end)
emu.register_frame_done(function()
  frame = frame + 1
  if plan[frame] then for _, fn in ipairs(plan[frame]) do fn() end end
  if frame > t0 + 700 then sp:write_u8(P1 + 0x288, 240); sp:write_u32(RANK, 0x800000); sp:write_u8(P1 + 0x25B, 2) end
  local st = sp:read_u8(STAGEB)
  if st ~= last_stage then out:write(string.format("STAGE f=%d %d -> %d ptr=%08X\n", frame, last_stage, st, sp:read_u32(SPTR))); last_stage = st; out:flush() end
  if frame >= MAXF then out:close(); m:exit() end
end)
