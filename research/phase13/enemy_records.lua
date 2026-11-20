-- sample BL enemy parts (0C286578, 192 x 0xB4) during stage 1; dump their type records (+08, +10)
local m = manager.machine; local sp = m.devices[":maincpu"].spaces["program"]
local ports = m.ioport.ports; local function fld(p, n) return ports[p].fields[n] end
local frame, seen = 0, {}
local plan = {}
local function at(f, fn) plan[f] = plan[f] or {}; table.insert(plan[f], fn) end
local function press(f, p, n, len) at(f, function() fld(p, n):set_value(1) end); at(f + (len or 6), function() fld(p, n):clear_value() end) end
local t0 = 2400
press(t0, ":PORT_C", "Coin 1", 8); press(t0 + 60, ":PORT_C", "1 Player Start", 8)
for i = 0, 8 do press(t0 + 300 + i * 40, ":PORT_D", "P1 Button 1", 6) end
at(t0 + 700, function() fld(":PORT_D", "P1 Button 1"):set_value(1) end)
local out = io.open(os.getenv("ENOUT"), "w")
emu.register_frame_done(function()
  frame = frame + 1
  if plan[frame] then for _, fn in ipairs(plan[frame]) do fn() end end
  if frame > t0 + 800 and frame % 30 == 0 then
    for i = 0, 191 do
      local a = 0x0C286578 + i * 0xB4
      if (sp:read_u32(a) & 0x80000000) ~= 0 then
        for _, off in ipairs({0x08, 0x10}) do
          local p = sp:read_u32(a + off)
          if p >= 0x0C000000 and p < 0x0C200000 and not seen[p] then
            seen[p] = true
            local t = {} for k = 0, 15 do t[#t + 1] = string.format("%08X", sp:read_u32(p + 4 * k)) end
            out:write(string.format("%d %02X %08X %s\n", frame, off, p, table.concat(t, " ")))
          end
        end
      end
    end
  end
  if frame == t0 + 5000 then out:close(); m:exit() end
end)
