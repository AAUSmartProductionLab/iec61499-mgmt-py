<?xml version='1.0' encoding='utf-8'?>
<AdapterType Name="AEquipment" Comment="An adapter: one connection from a skill's run (the plug) to its equipment's port (EP_, the socket) that carries a command out and the word that it was played back. Technical: What a skill's run (SKILL_Run, the plug) sends its equipment's port (EP_, the socket): SEND a command; PLAYED comes back when all its phases are out">
  <Identification Standard="61499-2" />
  <VersionInfo Organization="AAU Smart Production Lab" Version="0.1" Author="Project contributors" Date="2026-09-28" />
  <CompilerInfo packageName="modlib" />
  <InterfaceList>
    <EventInputs>
      <Event Name="PLAYED" Type="Event" Comment="All phases of the command were sent" />
    </EventInputs>
    <EventOutputs>
      <Event Name="SEND" Type="Event" Comment="Send a command to the equipment: its output values, phase by phase">
        <With Var="Holder" />
        <With Var="Command" />
        <With Var="Arg" />
        <With Var="Release" />
      </Event>
    </EventOutputs>
    <InputVars />
    <OutputVars>
      <VarDeclaration Name="Holder" Type="WSTRING" Comment="Who sends the command" />
      <VarDeclaration Name="Command" Type="USINT" Comment="The command's code" />
      <VarDeclaration Name="Arg" Type="LREAL" Comment="The command's argument (e.g. a position)" />
      <VarDeclaration Name="Release" Type="BOOL" Comment="Give up the equipment after the command" />
    </OutputVars>
  </InterfaceList>
</AdapterType>