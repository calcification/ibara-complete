-- research/phase29: BL (MAME) item spawns per frame around a bomb (HOLD=8) or the Hadou (HOLD=140); env TYPE (0-3), BOMBS (frames), HOLD, END, OUT; bombs kept at 3 and rank at 0x600000 until frame 1700
-- BL: pick straight type TYPE (env, 0=A..3=D), play stage 1 holding shot, bomb at BOMB frames; log new items
local m = manager.machine; local sp = m.devices[":maincpu"].spaces["program"]
local ports = m.ioport.ports; local function fld(p, n) return ports[p].fields[n] end
local frame = 0; local plan = {}
local function at(f, fn) plan[f] = plan[f] or {}; table.insert(plan[f], fn) end
local function press(f, p, n, len) at(f, function() fld(p, n):set_value(1) end); at(f + (len or 6), function() fld(p, n):clear_value() end) end
local t0 = 2400
local TYPE = tonumber(os.getenv("TYPE") or "1")
press(t0, ":PORT_C", "Coin 1", 8); press(t0 + 60, ":PORT_C", "1 Player Start", 8)
press(t0 + 300, ":PORT_D", "P1 Button 1", 6)
for i = 1, TYPE do press(t0 + 300 + 40 * i, ":PORT_D", "P1 Down", 6) end
press(t0 + 500, ":PORT_D", "P1 Button 1", 6)
at(t0 + 900, function() fld(":PORT_D", "P1 Button 1"):set_value(1) end)
local bombs = {}
for f in string.gmatch(os.getenv("BOMBS") or "", "%d+") do bombs[#bombs + 1] = tonumber(f) end
local HOLD = tonumber(os.getenv("HOLD") or "8")
for _, f in ipairs(bombs) do press(t0 + f, ":PORT_D", "P1 Button 2", HOLD) end
local POOL, N, ST = 0x0C3BC7CC, 256, 0x60
for _, f in ipairs({1790, 1830, 1880, 1930, 1942, 1950, 1960, 1975, 2000}) do at(t0 + f, function() m.video:snapshot() end) end
local P1 = 0x0C29D1D8
local alive = {}
local out = io.open(os.getenv("OUT"), "w")
emu.register_frame_done(function()
  frame = frame + 1
  if plan[frame] then for _, fn in ipairs(plan[frame]) do fn() end end
  if frame < t0 + 900 then return end
  sp:write_u8(P1 + 0x288, 240)
  if frame < t0 + 1700 then sp:write_u8(P1 + 0x25D, 3); sp:write_u32(0x0C297A3C, 0x600000) end
  for i = 0, N - 1 do
    local a = POOL + i * ST
    local on = (sp:read_u32(a) & 0x80000000) ~= 0
    if on and not alive[i] then
      out:write(string.format("%d %d type %d sub %d w8 %08X\n", frame - t0, i, sp:read_u32(a + 4), sp:read_u32(a + 8), sp:read_u32(a + 0xC)))
    end
    alive[i] = on
  end
  if frame >= t0 + tonumber(os.getenv("END") or "3000") then out:close(); m:exit() end
end)
