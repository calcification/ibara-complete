local done=false
emu.register_frame_done(function()
  if done then return end; done=true
  for tag,port in pairs(manager.machine.ioport.ports) do
    for name,field in pairs(port.fields) do print("PORT", tag, "|", name) end
  end
end)
