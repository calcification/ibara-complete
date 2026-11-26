-- Optional damage trace for tools/stage_compare/bl_stage_log.lua. Run with -nodrc.
return function(cpu, directory, stage_frame)
  local space = cpu.spaces["program"]
  local first, stride, count = 0x0C286578, 0xB4, 192
  local trace_start = tonumber(os.getenv("CONTACT_START") or "10000")
  local out = assert(io.open(directory .. "/contacts.txt", "w"))
  local core_writes = assert(io.open(directory .. "/core-writes.txt", "w"))
  local read_tap, write_tap
  local busy, closed = false, false

  local function shot(caller)
    local frame_pointer = cpu.state["R14"].value
    local pointer = space:read_u32(frame_pointer + (caller == 0x0C06E404 and 36 or 28))
    if pointer < 0x0C000000 or pointer >= 0x0C800000 then return -1 end
    return space:read_u32(pointer + 4) & 0xFF
  end

  local function lane(value, shift, bits)
    local full = (1 << bits) - 1
    -- The Lua binding represents unsigned masks above INT64_MAX as floats.
    -- A selected lane in the high half has enough precision after shifting.
    if math.type(value) == "float" then
      if value >= 2.0 ^ 64 then return full end
      return math.floor(value / 2.0 ^ shift) % (full + 1)
    end
    return (value >> shift) & full
  end

  local function event(action, offset, data, mask, field, bits)
    if busy or closed then return end
    local pc = cpu.state["PC"].value
    if action == "C" then
      if pc < 0x0C0A8F0A or pc > 0x0C0A8F0C then return end
    end
    local raw_caller = cpu.state["PR"].value
    local native_damage_path = pc >= 0x0C0A8E90 and pc <= 0x0C0A9020
    local caller = raw_caller
    if native_damage_path then
      -- Resolving a parent link calls a helper. PR now points inside damage,
      -- while its own frame still has the original caller at R14+8.
      caller = space:read_u32(cpu.state["R14"].value + 8)
    end
    local shot_caller = caller == 0x0C06E404 or caller == 0x0C06E79C
    if action == "C" and not shot_caller then return end
    local a = offset + ((first + field - offset) % 4)
    if ((a - first - field) % stride) ~= 0 then a = a + 4 end
    if ((a - first - field) % stride) ~= 0 then return end
    local part = a - field
    if part < first or part >= first + count * stride then return end
    local shift = (8 - (a - offset) - (bits // 8)) * 8
    if shift < 0 then return end
    local bitmask = (1 << bits) - 1
    if lane(mask, shift, bits) ~= bitmask then return end
    busy = true
    local kind = space:read_u32(part + 4)
    if kind == 74 or kind == 79 then
      local hp = space:read_u16(part + 0x3C)
      local value = lane(data, shift, bits)
      local subtype = space:read_u32(part + 8)
      if action == "H" and kind == 74 and (subtype == 0 or subtype == 2) and value < hp then
        core_writes:write(string.format("%d %d %d %d %d %08X %08X\n",
          stage_frame(), (part - first) // stride, subtype, hp, value, pc, raw_caller))
      end
      if hp > 0 and (action == "C" or (shot_caller and native_damage_path and value < hp)) then
        out:write(string.format("%s %d %d %d %d %d %d %08X %d\n",
          action, stage_frame(), (part - first) // stride, kind,
          subtype, hp, value, caller, shot(caller)))
      end
    end
    busy = false
  end

  -- Leave the previous stages and the start of Stage 6 outside the taps.
  emu.register_frame_done(function()
    if closed or read_tap or stage_frame() < trace_start then return end
    read_tap = space:install_read_tap(first & ~7, (first + count * stride - 1) | 7, "rose_contact",
      function(offset, data, mask) event("C", offset, data, mask, 0x84, 8) end)
    write_tap = space:install_write_tap(first & ~7, (first + count * stride - 1) | 7, "rose_hp",
      function(offset, data, mask) event("H", offset, data, mask, 0x3C, 16) end)
  end)

  return function()
    closed = true
    if read_tap then read_tap:remove() end
    if write_tap then write_tap:remove() end
    out:close()
    core_writes:close()
  end
end
