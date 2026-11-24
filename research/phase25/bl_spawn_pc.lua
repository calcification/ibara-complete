-- mame ibarablk -rompath ROMS -video none -sound none -nothrottle -nodrc -autoboot_script bl_spawn_pc.lua
-- env OUT, STAGE (BL stage byte, default 6 = stage 5), TYPE (enemy type, default 52), MAXF.
-- Plays like tools/stage_compare/bl_stage_log.lua (invincible P1, shot held, rank 0x800000, shot level 2) and, while
-- STAGE runs, logs every store of TYPE to an enemy part's type field (+4): stage frame, part slot, writer PC, PR and
-- R0-R14 (to find the stage script pointer). research/phase25.
local m = manager.machine; local cpu = m.devices[":maincpu"]; local sp = cpu.spaces["program"]
local ports = m.ioport.ports; local function fld(p, n) return ports[p].fields[n] end
local P1, EN, RANK, STAGEB = 0x0C29D1D8, 0x0C286578, 0x0C297A3C, 0x0C3C4170
local STAGE = tonumber(os.getenv("STAGE") or "6"); local TYPE = tonumber(os.getenv("TYPE") or "52")
local MAXF = tonumber(os.getenv("MAXF") or "60000")
local out = io.open(assert(os.getenv("OUT")), "w")
local frame, sf = 0, -1
local plan = {}
local function at(f, fn) plan[f] = plan[f] or {}; table.insert(plan[f], fn) end
local function press(f, p, n, len) at(f, function() fld(p, n):set_value(1) end); at(f + (len or 6), function() fld(p, n):clear_value() end) end
local t0 = 2400
press(t0, ":PORT_C", "Coin 1", 8); press(t0 + 60, ":PORT_C", "1 Player Start", 8)
for i = 0, 8 do press(t0 + 300 + i * 40, ":PORT_D", "P1 Button 1", 6) end
at(t0 + 700, function() fld(":PORT_D", "P1 Button 1"):set_value(1) end)
TAP = sp:install_write_tap(EN & ~7, (EN + 192 * 0xB4) | 7, "en", function(offset, data, mask)
  if sf < 0 then return end
  for half = 0, 1 do
    local a = offset + half * 4
    local mk = (mask >> (32 * (1 - half))) & 0xFFFFFFFF
    local v = (data >> (32 * (1 - half))) & 0xFFFFFFFF
    if mk == 0xFFFFFFFF and a >= EN and (a - EN) % 0xB4 == 4 and v == TYPE then
      local regs = ""
      for r = 0, 14 do regs = regs .. string.format(" R%d=%08X", r, cpu.state["R" .. r].value) end
      out:write(string.format("f=%d slot=%d pc=%08X pr=%08X script=%08X%s\n", sf, (a - EN) // 0xB4, cpu.state["PC"].value,
        cpu.state["PR"].value, sp:read_u32(0x0C2ABAA4), regs))
    end
  end
end)
emu.register_frame_done(function()
  frame = frame + 1
  if plan[frame] then for _, fn in ipairs(plan[frame]) do fn() end end
  if frame <= t0 + 700 then return end
  sp:write_u8(P1 + 0x288, 240); sp:write_u32(RANK, 0x800000); sp:write_u8(P1 + 0x25B, 2)
  local st = sp:read_u8(STAGEB)
  if st == STAGE and sf < 0 then
    local p0 = sp:read_u32(0x0C2ABAA4); out:write(string.format("start script=%08X\n", p0))
    local d = io.open(os.getenv("OUT") .. ".script", "wb"); local base = (p0 & ~0xFFF) - 0x4000
    out:write(string.format("dump base=%08X\n", base))
    for a = base, base + 0x20000 - 1 do d:write(string.char(sp:read_u8(a))) end; d:close()
  end
  if st == STAGE then sf = sf < 0 and 0 or sf + 1 elseif sf >= 0 and st > STAGE then out:close(); m:exit() end
  if frame > MAXF then out:close(); m:exit() end
end)
