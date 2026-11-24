-- Replay a PCB run in MAME one game update at a time (tools/pcb_tap). Study tool; writes only input ports.
--
--   UPDATES=run1.updates OUT=run1.mame mame ibara -rompath ROMS -nodrc -nonvram_save \
--       -autoboot_script tools/pcb_tap/mame_replay.lua [-video none -sound none -nothrottle]
--
-- Start MAME with the same settings and NVRAM as the board (the run begins at power-on on both). Each time the
-- game's update counter (TICK, default 0x0C21F880 = base Ibara, U4 d5fb6657; research/phase22) advances, the next
-- update's inputs are applied, so a hold on one machine but not the other cannot shift the inputs. Until the
-- counter first moves (boot), inputs follow the PCB refresh by refresh.
-- Output per refresh: "refresh tick advanced update [x y]" (TICK 0x0C2380B0 and PLAYER 0x0C29D1D8 for ibarablk). Pair it with the .updates file in compare.py.
local machine = manager.machine
local ram = machine.devices[":maincpu"].spaces.program
local ports = machine.ioport.ports
local TICK = tonumber(os.getenv("TICK") or "0x0C21F880")
local NAMES = {{":PORT_D", "P1 Up"}, {":PORT_D", "P1 Down"}, {":PORT_D", "P1 Left"}, {":PORT_D", "P1 Right"},
  {":PORT_D", "P1 Button 1"}, {":PORT_D", "P1 Button 2"}, {":PORT_D", "P1 Button 3"},
  {":PORT_C", "1 Player Start"}, {":PORT_C", "Coin 1"}}
local fields = {}
for i, pn in ipairs(NAMES) do fields[i] = assert(ports[pn[1]] and ports[pn[1]].fields[pn[2]], pn[2]) end

local updates = {}
for line in io.lines((assert(os.getenv("UPDATES"), "set UPDATES"))) do
  if line:sub(1, 1) ~= "#" and #line > 0 then
    local u, frame, holds, bits = line:match("(%d+) (%d+) (%d+) (%x+)")
    updates[#updates + 1] = {frame = tonumber(frame), bits = tonumber(bits, 16)}
  end
end
local out = assert(io.open(assert(os.getenv("OUT"), "set OUT"), "w"))
local PLAYER = os.getenv("PLAYER") and tonumber(os.getenv("PLAYER"))  -- optional: P1 record, x/y at +0x10/+0x14
out:write("# refresh tick advanced update" .. (PLAYER and " x y" or "") .. "\n")

local current = -1
local function apply(bits)
  if bits == current then return end
  for i, f in ipairs(fields) do
    if (bits >> (i - 1)) & 1 == 1 then f:set_value(1) else f:clear_value() end
  end
  current = bits
end

local refresh, last_tick, started, k = 0, nil, false, 1
emu.register_frame_done(function()
  local tick = ram:read_u32(TICK)
  local advanced = last_tick ~= nil and tick ~= last_tick
  if advanced and not started and tick ~= 0 then started = true end
  if not started then
    -- boot: follow the PCB refresh by refresh (no slowdown before gameplay)
    while k <= #updates and updates[k].frame <= refresh do k = k + 1 end
    if updates[k] then apply(updates[k].bits) end
  elseif advanced then
    k = k + 1
    if updates[k] then apply(updates[k].bits) else out:close(); machine:exit() end
  end
  local pos = PLAYER and string.format(" %d %d", ram:read_i32(PLAYER + 0x10), ram:read_i32(PLAYER + 0x14)) or ""
  out:write(string.format("%d %d %d %d%s\n", refresh, tick, advanced and 1 or 0, k - 1, pos))
  last_tick = tick
  refresh = refresh + 1
end)
