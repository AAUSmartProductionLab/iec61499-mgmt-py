<?xml version='1.0' encoding='utf-8'?>
<AdapterType Name="AContract" Comment="An adapter: one connection from a primitive's contract (SC_, the plug) to its run (SKILL_Run, the socket) that carries what the contract says: at the start what to do and whether it may start, at each new state of the equipment whether it is done and may go on. Technical: What a skill primitive's contract (SC_, the plug) tells its run (SKILL_Run, the socket): at START what to do and whether it may start, at SAMPLE whether the newest state of the equipment ends the run">
  <Identification Standard="61499-2" />
  <VersionInfo Organization="AAU Smart Production Lab" Version="0.1" Author="Project contributors" Date="2026-09-28" />
  <CompilerInfo packageName="modlib" />
  <InterfaceList>
    <EventInputs />
    <EventOutputs>
      <Event Name="START" Type="Event" Comment="A run starts: what to do (Command, Arg, RunTime, StopCommand) and whether it may (Pre)">
        <With Var="Pre" />
        <With Var="Post" />
        <With Var="Timed" />
        <With Var="RunTime" />
        <With Var="Command" />
        <With Var="Arg" />
        <With Var="StopCommand" />
      </Event>
      <Event Name="SAMPLE" Type="Event" Comment="The equipment's newest state, judged: is the skill done (Post), may it go on (Inv)">
        <With Var="Post" />
        <With Var="Inv" />
        <With Var="EqHolder" />
      </Event>
    </EventOutputs>
    <InputVars />
    <OutputVars>
      <VarDeclaration Name="Pre" Type="BOOL" />
      <VarDeclaration Name="Post" Type="BOOL" />
      <VarDeclaration Name="Timed" Type="BOOL" />
      <VarDeclaration Name="RunTime" Type="TIME" />
      <VarDeclaration Name="Command" Type="USINT" />
      <VarDeclaration Name="Arg" Type="LREAL" />
      <VarDeclaration Name="StopCommand" Type="USINT" />
      <VarDeclaration Name="Inv" Type="BOOL" />
      <VarDeclaration Name="EqHolder" Type="WSTRING" Comment="Who holds the equipment now (empty: free)" />
    </OutputVars>
  </InterfaceList>
</AdapterType>