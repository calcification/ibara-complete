-- research/phase33: rose constructor calls (BL 0C0A8090), for tools/stage_compare/bl_stage_log.lua CONTACT_TAP
-- (run with -nodrc). On the primary part's type write (PC 0C0A8108) logs: stage frame, caller return address
-- (the constructor's saved PR at R14+32), kind (first stack word, R14+0; the linked part gets subtype kind&3 + 1),
Output: rosekind.txt "frame caller kind slot".
return function(cpu, directory, stage_frame)
  local space = cpu.spaces["program"]
  local first, stride, count = 0x0C286578, 0xB4, 192
  local out = assert(io.open(directory .. "/rosekind.txt", "w"))
  local tap
  local closed = false
  local last
  tap = space:install_write_tap(first, first + stride * count - 1, "rosekind", function(offset, data, mask)
    if closed then return end
    local pc = cpu.state["PC"].value
    if pc < 0x0C0A8104 or pc > 0x0C0A8112 then return end
    local r14, r9 = cpu.state["R14"].value, cpu.state["R9"].value
    if r9 == last then return end  -- one line per part (the constructor's first writes all hit the same record)
    last = r9
    out:write(string.format("%d %08X %d %d\n", stage_frame(), space:read_u32(r14 + 32), space:read_u32(r14), (r9 - first) // stride))
  end)
  return function() closed = true; out:close(); if tap then tap:remove() end end
end
