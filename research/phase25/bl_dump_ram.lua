-- mame ibarablk -rompath ROMS -video none -sound none -nothrottle -autoboot_script bl_dump_ram.lua (env OUT, AT frames)
-- Starts a game and writes BL main RAM 0C000000-0C7FFFFF (big-endian, as the CPU sees it) to OUT. research/phase25.
local m = manager.machine; local sp = m.devices[":maincpu"].spaces["program"]
local ports = m.ioport.ports; local function fld(p, n) return ports[p].fields[n] end
local AT = tonumber(os.getenv("AT") or "3600"); local frame = 0
emu.register_frame_done(function()
  frame = frame + 1
  if frame == 2400 then fld(":PORT_C", "Coin 1"):set_value(1) elseif frame == 2408 then fld(":PORT_C", "Coin 1"):clear_value() end
  if frame == 2460 then fld(":PORT_C", "1 Player Start"):set_value(1) elseif frame == 2468 then fld(":PORT_C", "1 Player Start"):clear_value() end
  if frame == AT then
    local f = io.open(os.getenv("OUT"), "wb")
    for a = 0x0C000000, 0x0C7FFFFF, 4 do f:write(string.pack(">I4", sp:read_u32(a))) end
    f:close(); m:exit()
  end
end)
