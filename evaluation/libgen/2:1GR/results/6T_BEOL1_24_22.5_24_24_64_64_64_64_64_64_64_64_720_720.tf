Technology {
  name = "PROBE" 
  unitTimeName = "ns" 
  timePrecision = 1000 
  unitLengthName = "micron" 
  lengthPrecision = 10000 
  unitVoltageName = "v" 
  voltagePrecision = 1000000 
  unitCurrentName = "ma" 
  currentPrecision = 1000 
  unitPowerName = "mw" 
  powerPrecision = 100000 
  unitResistanceName = "kohm" 
  resistancePrecision = 10000000 
  unitCapacitanceName = "pf" 
  capacitancePrecision = 10000000 
  unitInductanceName = "nh" 
  inductancePrecision = 100 
  gridResolution = 1 
  minEdgeMode = 1 
  metalAboveMiMCap = "metal14"
}

Layer "M0" { 
  layerNumber = 15 
  maskName = "metal0" 
  onWireTrack = 1
  isDefaultLayer = 1 
  visible = 1 
  selectable = 1
  blink = 0 
  lineStyle = "solid"
  pattern = "dot"
  color = "green" 
  pitch = 0.0240
  defaultWidth = 0.0140
  minWidth = 0.0140
  minSpacing = 0.0100
  minArea = 0.0003
  endOfLine1NeighborEndToEndThreshold = 0.0240
  endOfLine1NeighborEndToEndThreshold2 = 0.0240
  endOfLine1NeighborEndToEndParallelWidth = 0.000 
  endOfLine1NeighborEndToEndMinSpacing = 0.0240
}

Layer "V0" { 
  layerNumber = 18 
  maskName = "via0"
  isDefaultLayer = 1
  visible = 1 
  selectable = 1
  blink = 0 
  lineStyle = "solid"
  pattern = "rectangleX" 
  color = "cyan"
  cutTblSize = 1 
  cutNameTbl = ( Vx )
  cutWidthTbl = ( 0.0112 )
  cutHeightTbl = ( 0.0112 )
  cutDataTypeTbl = ( 0 ) 
  enclosureTblSize = 4
  enclosureTbl = ( Vx, -1.0, -1.0, 0.0035, 0.0, -1.0, -1.0,
                 Vx, -1.0, -1.0, 0.0, 0.0035, -1.0, -1.0,
                 Vx, 0.0035, 0.0, -1.0, -1.0, -1.0, -1.0,
                 Vx, 0.0, 0.0035, -1.0, -1.0, -1.0, -1.0)
}

Layer "M1" { 
  layerNumber = 19 
  maskName = "metal1" 
  onWireTrack = 1
  isDefaultLayer = 1 
  visible = 1 
  selectable = 1
  blink = 0 
  lineStyle = "solid"
  pattern = "dot"
  color = "green" 
  pitch = 0.0225
  defaultWidth = 0.0150
  minWidth = 0.0150
  minSpacing = 0.0075
  minArea = 0.0003
  endOfLine1NeighborEndToEndThreshold = 0.0225
  endOfLine1NeighborEndToEndThreshold2 = 0.0225
  endOfLine1NeighborEndToEndParallelWidth = 0.000 
  endOfLine1NeighborEndToEndMinSpacing = 0.0225
}

Layer "V1" { 
  layerNumber = 21 
  maskName = "via1"
  isDefaultLayer = 1
  visible = 1 
  selectable = 1
  blink = 0 
  lineStyle = "solid"
  pattern = "rectangleX" 
  color = "cyan"
  cutTblSize = 1 
  cutNameTbl = ( Vx )
  cutWidthTbl = ( 0.0112 )
  cutHeightTbl = ( 0.0112 )
  cutDataTypeTbl = ( 0 ) 
  enclosureTblSize = 4
  enclosureTbl = ( Vx, -1.0, -1.0, 0.0035, 0.0, -1.0, -1.0,
                 Vx, -1.0, -1.0, 0.0, 0.0035, -1.0, -1.0,
                 Vx, 0.0035, 0.0, -1.0, -1.0, -1.0, -1.0,
                 Vx, 0.0, 0.0035, -1.0, -1.0, -1.0, -1.0)
}

Layer "M2" { 
  layerNumber = 20 
  maskName = "metal2" 
  onWireTrack = 1
  isDefaultLayer = 1 
  visible = 1 
  selectable = 1
  blink = 0 
  lineStyle = "solid"
  pattern = "dot"
  color = "green" 
  pitch = 0.0240
  defaultWidth = 0.0140
  minWidth = 0.0140
  minSpacing = 0.0100
  minArea = 0.0003
  endOfLine1NeighborEndToEndThreshold = 0.0240
  endOfLine1NeighborEndToEndThreshold2 = 0.0240
  endOfLine1NeighborEndToEndParallelWidth = 0.000 
  endOfLine1NeighborEndToEndMinSpacing = 0.0240
}

Layer "V2" { 
  layerNumber = 22 
  maskName = "via2"
  isDefaultLayer = 1
  visible = 1 
  selectable = 1
  blink = 0 
  lineStyle = "solid"
  pattern = "rectangleX" 
  color = "cyan"
  cutTblSize = 1 
  cutNameTbl = ( Vx )
  cutWidthTbl = ( 0.0140 )
  cutHeightTbl = ( 0.0140 )
  cutDataTypeTbl = ( 0 ) 
  enclosureTblSize = 4
  enclosureTbl = ( Vx, -1.0, -1.0, 0.0035, 0.0, -1.0, -1.0,
                 Vx, -1.0, -1.0, 0.0, 0.0035, -1.0, -1.0,
                 Vx, 0.0035, 0.0, -1.0, -1.0, -1.0, -1.0,
                 Vx, 0.0, 0.0035, -1.0, -1.0, -1.0, -1.0)
}

Layer "M3" { 
  layerNumber = 23 
  maskName = "metal3" 
  onWireTrack = 1
  isDefaultLayer = 1 
  visible = 1 
  selectable = 1
  blink = 0 
  lineStyle = "solid"
  pattern = "dot"
  color = "green" 
  pitch = 0.0240
  defaultWidth = 0.0140
  minWidth = 0.0140
  minSpacing = 0.0100
  minArea = 0.0003
  endOfLine1NeighborEndToEndThreshold = 0.0240
  endOfLine1NeighborEndToEndThreshold2 = 0.0240
  endOfLine1NeighborEndToEndParallelWidth = 0.000 
  endOfLine1NeighborEndToEndMinSpacing = 0.0240
}

Layer "V3" { 
  layerNumber = 24 
  maskName = "via3"
  isDefaultLayer = 1
  visible = 1 
  selectable = 1
  blink = 0 
  lineStyle = "solid"
  pattern = "rectangleX" 
  color = "cyan"
  cutTblSize = 1 
  cutNameTbl = ( Vx )
  cutWidthTbl = ( 0.0140 )
  cutHeightTbl = ( 0.0140 )
  cutDataTypeTbl = ( 0 ) 
  enclosureTblSize = 4
  enclosureTbl = ( Vx, -1.0, -1.0, 0.0035, 0.0, -1.0, -1.0,
                 Vx, -1.0, -1.0, 0.0, 0.0035, -1.0, -1.0,
                 Vx, 0.0035, 0.0, -1.0, -1.0, -1.0, -1.0,
                 Vx, 0.0, 0.0035, -1.0, -1.0, -1.0, -1.0)
}

Layer "M4" { 
  layerNumber = 25 
  maskName = "metal4" 
  onWireTrack = 1
  isDefaultLayer = 1 
  visible = 1 
  selectable = 1
  blink = 0 
  lineStyle = "solid"
  pattern = "dot"
  color = "green" 
  pitch = 0.0640
  defaultWidth = 0.0320
  minWidth = 0.0320
  minSpacing = 0.0320
  minArea = 0.0020
  endOfLine1NeighborEndToEndThreshold = 0.0640
  endOfLine1NeighborEndToEndThreshold2 = 0.0640
  endOfLine1NeighborEndToEndParallelWidth = 0.000 
  endOfLine1NeighborEndToEndMinSpacing = 0.0640
}

Layer "V4" { 
  layerNumber = 26 
  maskName = "via4"
  isDefaultLayer = 1
  visible = 1 
  selectable = 1
  blink = 0 
  lineStyle = "solid"
  pattern = "rectangleX" 
  color = "cyan"
  cutTblSize = 1 
  cutNameTbl = ( Vx )
  cutWidthTbl = ( 0.0320 )
  cutHeightTbl = ( 0.0320 )
  cutDataTypeTbl = ( 0 ) 
  enclosureTblSize = 4
  enclosureTbl = ( Vx, -1.0, -1.0, 0.0035, 0.0, -1.0, -1.0,
                 Vx, -1.0, -1.0, 0.0, 0.0035, -1.0, -1.0,
                 Vx, 0.0035, 0.0, -1.0, -1.0, -1.0, -1.0,
                 Vx, 0.0, 0.0035, -1.0, -1.0, -1.0, -1.0)
}

Layer "M5" { 
  layerNumber = 27 
  maskName = "metal5" 
  onWireTrack = 1
  isDefaultLayer = 1 
  visible = 1 
  selectable = 1
  blink = 0 
  lineStyle = "solid"
  pattern = "dot"
  color = "green" 
  pitch = 0.0640
  defaultWidth = 0.0320
  minWidth = 0.0320
  minSpacing = 0.0320
  minArea = 0.0020
  endOfLine1NeighborEndToEndThreshold = 0.0640
  endOfLine1NeighborEndToEndThreshold2 = 0.0640
  endOfLine1NeighborEndToEndParallelWidth = 0.000 
  endOfLine1NeighborEndToEndMinSpacing = 0.0640
}

Layer "V5" { 
  layerNumber = 28 
  maskName = "via5"
  isDefaultLayer = 1
  visible = 1 
  selectable = 1
  blink = 0 
  lineStyle = "solid"
  pattern = "rectangleX" 
  color = "cyan"
  cutTblSize = 1 
  cutNameTbl = ( Vx )
  cutWidthTbl = ( 0.0320 )
  cutHeightTbl = ( 0.0320 )
  cutDataTypeTbl = ( 0 ) 
  enclosureTblSize = 4
  enclosureTbl = ( Vx, -1.0, -1.0, 0.0035, 0.0, -1.0, -1.0,
                 Vx, -1.0, -1.0, 0.0, 0.0035, -1.0, -1.0,
                 Vx, 0.0035, 0.0, -1.0, -1.0, -1.0, -1.0,
                 Vx, 0.0, 0.0035, -1.0, -1.0, -1.0, -1.0)
}

Layer "M6" { 
  layerNumber = 29 
  maskName = "metal6" 
  onWireTrack = 1
  isDefaultLayer = 1 
  visible = 1 
  selectable = 1
  blink = 0 
  lineStyle = "solid"
  pattern = "dot"
  color = "green" 
  pitch = 0.0640
  defaultWidth = 0.0320
  minWidth = 0.0320
  minSpacing = 0.0320
  minArea = 0.0020
  endOfLine1NeighborEndToEndThreshold = 0.0640
  endOfLine1NeighborEndToEndThreshold2 = 0.0640
  endOfLine1NeighborEndToEndParallelWidth = 0.000 
  endOfLine1NeighborEndToEndMinSpacing = 0.0640
}

Layer "V6" { 
  layerNumber = 30 
  maskName = "via6"
  isDefaultLayer = 1
  visible = 1 
  selectable = 1
  blink = 0 
  lineStyle = "solid"
  pattern = "rectangleX" 
  color = "cyan"
  cutTblSize = 1 
  cutNameTbl = ( Vx )
  cutWidthTbl = ( 0.0320 )
  cutHeightTbl = ( 0.0320 )
  cutDataTypeTbl = ( 0 ) 
  enclosureTblSize = 4
  enclosureTbl = ( Vx, -1.0, -1.0, 0.0035, 0.0, -1.0, -1.0,
                 Vx, -1.0, -1.0, 0.0, 0.0035, -1.0, -1.0,
                 Vx, 0.0035, 0.0, -1.0, -1.0, -1.0, -1.0,
                 Vx, 0.0, 0.0035, -1.0, -1.0, -1.0, -1.0)
}

Layer "M7" { 
  layerNumber = 31 
  maskName = "metal7" 
  onWireTrack = 1
  isDefaultLayer = 1 
  visible = 1 
  selectable = 1
  blink = 0 
  lineStyle = "solid"
  pattern = "dot"
  color = "green" 
  pitch = 0.0640
  defaultWidth = 0.0320
  minWidth = 0.0320
  minSpacing = 0.0320
  minArea = 0.0020
  endOfLine1NeighborEndToEndThreshold = 0.0640
  endOfLine1NeighborEndToEndThreshold2 = 0.0640
  endOfLine1NeighborEndToEndParallelWidth = 0.000 
  endOfLine1NeighborEndToEndMinSpacing = 0.0640
}

Layer "V7" { 
  layerNumber = 32 
  maskName = "via7"
  isDefaultLayer = 1
  visible = 1 
  selectable = 1
  blink = 0 
  lineStyle = "solid"
  pattern = "rectangleX" 
  color = "cyan"
  cutTblSize = 1 
  cutNameTbl = ( Vx )
  cutWidthTbl = ( 0.0320 )
  cutHeightTbl = ( 0.0320 )
  cutDataTypeTbl = ( 0 ) 
  enclosureTblSize = 4
  enclosureTbl = ( Vx, -1.0, -1.0, 0.0035, 0.0, -1.0, -1.0,
                 Vx, -1.0, -1.0, 0.0, 0.0035, -1.0, -1.0,
                 Vx, 0.0035, 0.0, -1.0, -1.0, -1.0, -1.0,
                 Vx, 0.0, 0.0035, -1.0, -1.0, -1.0, -1.0)
}

Layer "M8" { 
  layerNumber = 33 
  maskName = "metal8" 
  onWireTrack = 1
  isDefaultLayer = 1 
  visible = 1 
  selectable = 1
  blink = 0 
  lineStyle = "solid"
  pattern = "dot"
  color = "green" 
  pitch = 0.0640
  defaultWidth = 0.0320
  minWidth = 0.0320
  minSpacing = 0.0320
  minArea = 0.0020
  endOfLine1NeighborEndToEndThreshold = 0.0640
  endOfLine1NeighborEndToEndThreshold2 = 0.0640
  endOfLine1NeighborEndToEndParallelWidth = 0.000 
  endOfLine1NeighborEndToEndMinSpacing = 0.0640
}

Layer "V8" { 
  layerNumber = 34 
  maskName = "via8"
  isDefaultLayer = 1
  visible = 1 
  selectable = 1
  blink = 0 
  lineStyle = "solid"
  pattern = "rectangleX" 
  color = "cyan"
  cutTblSize = 1 
  cutNameTbl = ( Vx )
  cutWidthTbl = ( 0.0320 )
  cutHeightTbl = ( 0.0320 )
  cutDataTypeTbl = ( 0 ) 
  enclosureTblSize = 4
  enclosureTbl = ( Vx, -1.0, -1.0, 0.0035, 0.0, -1.0, -1.0,
                 Vx, -1.0, -1.0, 0.0, 0.0035, -1.0, -1.0,
                 Vx, 0.0035, 0.0, -1.0, -1.0, -1.0, -1.0,
                 Vx, 0.0, 0.0035, -1.0, -1.0, -1.0, -1.0)
}

Layer "M9" { 
  layerNumber = 35 
  maskName = "metal9" 
  onWireTrack = 1
  isDefaultLayer = 1 
  visible = 1 
  selectable = 1
  blink = 0 
  lineStyle = "solid"
  pattern = "dot"
  color = "green" 
  pitch = 0.0640
  defaultWidth = 0.0320
  minWidth = 0.0320
  minSpacing = 0.0320
  minArea = 0.0020
  endOfLine1NeighborEndToEndThreshold = 0.0640
  endOfLine1NeighborEndToEndThreshold2 = 0.0640
  endOfLine1NeighborEndToEndParallelWidth = 0.000 
  endOfLine1NeighborEndToEndMinSpacing = 0.0640
}

Layer "V9" { 
  layerNumber = 36 
  maskName = "via9"
  isDefaultLayer = 1
  visible = 1 
  selectable = 1
  blink = 0 
  lineStyle = "solid"
  pattern = "rectangleX" 
  color = "cyan"
  cutTblSize = 1 
  cutNameTbl = ( Vx )
  cutWidthTbl = ( 0.0320 )
  cutHeightTbl = ( 0.0320 )
  cutDataTypeTbl = ( 0 ) 
  enclosureTblSize = 4
  enclosureTbl = ( Vx, -1.0, -1.0, 0.0035, 0.0, -1.0, -1.0,
                 Vx, -1.0, -1.0, 0.0, 0.0035, -1.0, -1.0,
                 Vx, 0.0035, 0.0, -1.0, -1.0, -1.0, -1.0,
                 Vx, 0.0, 0.0035, -1.0, -1.0, -1.0, -1.0)
}

Layer "M10" { 
  layerNumber = 37 
  maskName = "metal10" 
  onWireTrack = 1
  isDefaultLayer = 1 
  visible = 1 
  selectable = 1
  blink = 0 
  lineStyle = "solid"
  pattern = "dot"
  color = "green" 
  pitch = 0.0640
  defaultWidth = 0.0320
  minWidth = 0.0320
  minSpacing = 0.0320
  minArea = 0.0020
  endOfLine1NeighborEndToEndThreshold = 0.0640
  endOfLine1NeighborEndToEndThreshold2 = 0.0640
  endOfLine1NeighborEndToEndParallelWidth = 0.000 
  endOfLine1NeighborEndToEndMinSpacing = 0.0640
}

Layer "V10" { 
  layerNumber = 38 
  maskName = "via10"
  isDefaultLayer = 1
  visible = 1 
  selectable = 1
  blink = 0 
  lineStyle = "solid"
  pattern = "rectangleX" 
  color = "cyan"
  cutTblSize = 1 
  cutNameTbl = ( Vx )
  cutWidthTbl = ( 0.0320 )
  cutHeightTbl = ( 0.0320 )
  cutDataTypeTbl = ( 0 ) 
  enclosureTblSize = 4
  enclosureTbl = ( Vx, -1.0, -1.0, 0.0035, 0.0, -1.0, -1.0,
                 Vx, -1.0, -1.0, 0.0, 0.0035, -1.0, -1.0,
                 Vx, 0.0035, 0.0, -1.0, -1.0, -1.0, -1.0,
                 Vx, 0.0, 0.0035, -1.0, -1.0, -1.0, -1.0)
}

Layer "M11" { 
  layerNumber = 39 
  maskName = "metal11" 
  onWireTrack = 1
  isDefaultLayer = 1 
  visible = 1 
  selectable = 1
  blink = 0 
  lineStyle = "solid"
  pattern = "dot"
  color = "green" 
  pitch = 0.0640
  defaultWidth = 0.0320
  minWidth = 0.0320
  minSpacing = 0.0320
  minArea = 0.0020
  endOfLine1NeighborEndToEndThreshold = 0.0640
  endOfLine1NeighborEndToEndThreshold2 = 0.0640
  endOfLine1NeighborEndToEndParallelWidth = 0.000 
  endOfLine1NeighborEndToEndMinSpacing = 0.0640
}

Layer "V11" { 
  layerNumber = 40 
  maskName = "via11"
  isDefaultLayer = 1
  visible = 1 
  selectable = 1
  blink = 0 
  lineStyle = "solid"
  pattern = "rectangleX" 
  color = "cyan"
  cutTblSize = 1 
  cutNameTbl = ( Vx )
  cutWidthTbl = ( 0.0320 )
  cutHeightTbl = ( 0.0320 )
  cutDataTypeTbl = ( 0 ) 
  enclosureTblSize = 4
  enclosureTbl = ( Vx, -1.0, -1.0, 0.0035, 0.0, -1.0, -1.0,
                 Vx, -1.0, -1.0, 0.0, 0.0035, -1.0, -1.0,
                 Vx, 0.0035, 0.0, -1.0, -1.0, -1.0, -1.0,
                 Vx, 0.0, 0.0035, -1.0, -1.0, -1.0, -1.0)
}

Layer "M12" { 
  layerNumber = 41 
  maskName = "metal12" 
  onWireTrack = 1
  isDefaultLayer = 1 
  visible = 1 
  selectable = 1
  blink = 0 
  lineStyle = "solid"
  pattern = "dot"
  color = "green" 
  pitch = 0.7200
  defaultWidth = 0.3600
  minWidth = 0.3600
  minSpacing = 0.3600
  minArea = 0.2592
  endOfLine1NeighborEndToEndThreshold = 0.7200
  endOfLine1NeighborEndToEndThreshold2 = 0.7200
  endOfLine1NeighborEndToEndParallelWidth = 0.000 
  endOfLine1NeighborEndToEndMinSpacing = 0.7200
}

Layer "V12" { 
  layerNumber = 42 
  maskName = "via12"
  isDefaultLayer = 1
  visible = 1 
  selectable = 1
  blink = 0 
  lineStyle = "solid"
  pattern = "rectangleX" 
  color = "cyan"
  cutTblSize = 1 
  cutNameTbl = ( Vx )
  cutWidthTbl = ( 0.3600 )
  cutHeightTbl = ( 0.3600 )
  cutDataTypeTbl = ( 0 ) 
  enclosureTblSize = 4
  enclosureTbl = ( Vx, -1.0, -1.0, 0.0035, 0.0, -1.0, -1.0,
                 Vx, -1.0, -1.0, 0.0, 0.0035, -1.0, -1.0,
                 Vx, 0.0035, 0.0, -1.0, -1.0, -1.0, -1.0,
                 Vx, 0.0, 0.0035, -1.0, -1.0, -1.0, -1.0)
}

Layer "M13" { 
  layerNumber = 43 
  maskName = "metal13" 
  onWireTrack = 1
  isDefaultLayer = 1 
  visible = 1 
  selectable = 1
  blink = 0 
  lineStyle = "solid"
  pattern = "dot"
  color = "green" 
  pitch = 0.7200
  defaultWidth = 0.3600
  minWidth = 0.3600
  minSpacing = 0.3600
  minArea = 0.2592
  endOfLine1NeighborEndToEndThreshold = 0.7200
  endOfLine1NeighborEndToEndThreshold2 = 0.7200
  endOfLine1NeighborEndToEndParallelWidth = 0.000 
  endOfLine1NeighborEndToEndMinSpacing = 0.7200
}

Layer "OUTLINE" { 
  layerNumber = 1 
  visible = 1 
  selectable = 1 
  blink = 0 
  lineStyle = "solid"
  pattern = "blank"
  color = "red" 
}

DesignRule {
 layer1 = "V0"
 layer2 = "V0"
 cut1TblSize = 1
 cut2TblSize = 1
 cut1NameTbl = (Vx)
 cut2NameTbl = (Vx)
 sameNetCenterMinSpacingTbl = (0.0318)
 diffNetCenterMinSpacingTbl = (0.0318)
}

DesignRule {
 layer1 = "V1"
 layer2 = "V1"
 cut1TblSize = 1
 cut2TblSize = 1
 cut1NameTbl = (Vx)
 cut2NameTbl = (Vx)
 sameNetCenterMinSpacingTbl = (0.0339)
 diffNetCenterMinSpacingTbl = (0.0339)
}

DesignRule {
 layer1 = "V2"
 layer2 = "V2"
 cut1TblSize = 1
 cut2TblSize = 1
 cut1NameTbl = (Vx)
 cut2NameTbl = (Vx)
 sameNetCenterMinSpacingTbl = (0.0339)
 diffNetCenterMinSpacingTbl = (0.0339)
}

DesignRule {
 layer1 = "V3"
 layer2 = "V3"
 cut1TblSize = 1
 cut2TblSize = 1
 cut1NameTbl = (Vx)
 cut2NameTbl = (Vx)
 sameNetCenterMinSpacingTbl = (0.0905)
 diffNetCenterMinSpacingTbl = (0.0905)
}

DesignRule {
 layer1 = "V4"
 layer2 = "V4"
 cut1TblSize = 1
 cut2TblSize = 1
 cut1NameTbl = (Vx)
 cut2NameTbl = (Vx)
 sameNetCenterMinSpacingTbl = (0.0905)
 diffNetCenterMinSpacingTbl = (0.0905)
}

DesignRule {
 layer1 = "V5"
 layer2 = "V5"
 cut1TblSize = 1
 cut2TblSize = 1
 cut1NameTbl = (Vx)
 cut2NameTbl = (Vx)
 sameNetCenterMinSpacingTbl = (0.0905)
 diffNetCenterMinSpacingTbl = (0.0905)
}

DesignRule {
 layer1 = "V6"
 layer2 = "V6"
 cut1TblSize = 1
 cut2TblSize = 1
 cut1NameTbl = (Vx)
 cut2NameTbl = (Vx)
 sameNetCenterMinSpacingTbl = (0.0905)
 diffNetCenterMinSpacingTbl = (0.0905)
}

DesignRule {
 layer1 = "V7"
 layer2 = "V7"
 cut1TblSize = 1
 cut2TblSize = 1
 cut1NameTbl = (Vx)
 cut2NameTbl = (Vx)
 sameNetCenterMinSpacingTbl = (0.0905)
 diffNetCenterMinSpacingTbl = (0.0905)
}

DesignRule {
 layer1 = "V8"
 layer2 = "V8"
 cut1TblSize = 1
 cut2TblSize = 1
 cut1NameTbl = (Vx)
 cut2NameTbl = (Vx)
 sameNetCenterMinSpacingTbl = (0.0905)
 diffNetCenterMinSpacingTbl = (0.0905)
}

DesignRule {
 layer1 = "V9"
 layer2 = "V9"
 cut1TblSize = 1
 cut2TblSize = 1
 cut1NameTbl = (Vx)
 cut2NameTbl = (Vx)
 sameNetCenterMinSpacingTbl = (0.0905)
 diffNetCenterMinSpacingTbl = (0.0905)
}

DesignRule {
 layer1 = "V10"
 layer2 = "V10"
 cut1TblSize = 1
 cut2TblSize = 1
 cut1NameTbl = (Vx)
 cut2NameTbl = (Vx)
 sameNetCenterMinSpacingTbl = (0.0905)
 diffNetCenterMinSpacingTbl = (0.0905)
}

DesignRule {
 layer1 = "V11"
 layer2 = "V11"
 cut1TblSize = 1
 cut2TblSize = 1
 cut1NameTbl = (Vx)
 cut2NameTbl = (Vx)
 sameNetCenterMinSpacingTbl = (1.0182)
 diffNetCenterMinSpacingTbl = (1.0182)
}

DesignRule {
 layer1 = "V12"
 layer2 = "V12"
 cut1TblSize = 1
 cut2TblSize = 1
 cut1NameTbl = (Vx)
 cut2NameTbl = (Vx)
 sameNetCenterMinSpacingTbl = (1.0182)
 diffNetCenterMinSpacingTbl = (1.0182)
}

ContactCode "V0_HV" {
  contactCodeNumber = 1
  cutLayer = "V0"
  lowerLayer = "M0"
  upperLayer = "M1"
  upperLayerEncWidth = 0.000
  upperLayerEncHeight = 0.0035
  lowerLayerEncWidth = 0.0035
  lowerLayerEncHeight = 0.0014000000000000002
  cutWidth = 0.0112
  cutHeight = 0.0112
  isDefaultContact = 1
}

ContactCode "V1_VH" {
  contactCodeNumber = 2
  cutLayer = "V1"
  lowerLayer = "M1"
  upperLayer = "M2"
  upperLayerEncWidth = 0.0035
  upperLayerEncHeight = 0.0014000000000000002
  lowerLayerEncWidth = 0.000
  lowerLayerEncHeight = 0.0035
  cutWidth = 0.0112
  cutHeight = 0.0112
  isDefaultContact = 1
}

ContactCode "V2_HV" {
  contactCodeNumber = 3
  cutLayer = "V2"
  lowerLayer = "M2"
  upperLayer = "M3"
  upperLayerEncWidth = 0.000
  upperLayerEncHeight = 0.0035
  lowerLayerEncWidth = 0.0035
  lowerLayerEncHeight = 0.000
  cutWidth = 0.0140
  cutHeight = 0.0140
  isDefaultContact = 1
}

ContactCode "V3_VH" {
  contactCodeNumber = 4
  cutLayer = "V3"
  lowerLayer = "M3"
  upperLayer = "M4"
  upperLayerEncWidth = 0.0035
  upperLayerEncHeight = 0.009000000000000001
  lowerLayerEncWidth = 0.000
  lowerLayerEncHeight = 0.0035
  cutWidth = 0.0140
  cutHeight = 0.0140
  isDefaultContact = 1
}

ContactCode "V4_HV" {
  contactCodeNumber = 5
  cutLayer = "V4"
  lowerLayer = "M4"
  upperLayer = "M5"
  upperLayerEncWidth = 0.000
  upperLayerEncHeight = 0.0035
  lowerLayerEncWidth = 0.0035
  lowerLayerEncHeight = 0.000
  cutWidth = 0.0320
  cutHeight = 0.0320
  isDefaultContact = 1
}

ContactCode "V5_VH" {
  contactCodeNumber = 6
  cutLayer = "V5"
  lowerLayer = "M5"
  upperLayer = "M6"
  upperLayerEncWidth = 0.0035
  upperLayerEncHeight = 0.000
  lowerLayerEncWidth = 0.000
  lowerLayerEncHeight = 0.0035
  cutWidth = 0.0320
  cutHeight = 0.0320
  isDefaultContact = 1
}

ContactCode "V6_HV" {
  contactCodeNumber = 7
  cutLayer = "V6"
  lowerLayer = "M6"
  upperLayer = "M7"
  upperLayerEncWidth = 0.000
  upperLayerEncHeight = 0.0035
  lowerLayerEncWidth = 0.0035
  lowerLayerEncHeight = 0.000
  cutWidth = 0.0320
  cutHeight = 0.0320
  isDefaultContact = 1
}

ContactCode "V7_VH" {
  contactCodeNumber = 8
  cutLayer = "V7"
  lowerLayer = "M7"
  upperLayer = "M8"
  upperLayerEncWidth = 0.0035
  upperLayerEncHeight = 0.000
  lowerLayerEncWidth = 0.000
  lowerLayerEncHeight = 0.0035
  cutWidth = 0.0320
  cutHeight = 0.0320
  isDefaultContact = 1
}

ContactCode "V8_HV" {
  contactCodeNumber = 9
  cutLayer = "V8"
  lowerLayer = "M8"
  upperLayer = "M9"
  upperLayerEncWidth = 0.000
  upperLayerEncHeight = 0.0035
  lowerLayerEncWidth = 0.0035
  lowerLayerEncHeight = 0.000
  cutWidth = 0.0320
  cutHeight = 0.0320
  isDefaultContact = 1
}

ContactCode "V9_VH" {
  contactCodeNumber = 10
  cutLayer = "V9"
  lowerLayer = "M9"
  upperLayer = "M10"
  upperLayerEncWidth = 0.0035
  upperLayerEncHeight = 0.000
  lowerLayerEncWidth = 0.000
  lowerLayerEncHeight = 0.0035
  cutWidth = 0.0320
  cutHeight = 0.0320
  isDefaultContact = 1
}

ContactCode "V10_HV" {
  contactCodeNumber = 11
  cutLayer = "V10"
  lowerLayer = "M10"
  upperLayer = "M11"
  upperLayerEncWidth = 0.000
  upperLayerEncHeight = 0.0035
  lowerLayerEncWidth = 0.0035
  lowerLayerEncHeight = 0.000
  cutWidth = 0.0320
  cutHeight = 0.0320
  isDefaultContact = 1
}

ContactCode "V11_VH" {
  contactCodeNumber = 12
  cutLayer = "V11"
  lowerLayer = "M11"
  upperLayer = "M12"
  upperLayerEncWidth = 0.0035
  upperLayerEncHeight = 0.16399999999999998
  lowerLayerEncWidth = 0.000
  lowerLayerEncHeight = 0.0035
  cutWidth = 0.0320
  cutHeight = 0.0320
  isDefaultContact = 1
}

ContactCode "V12_HV" {
  contactCodeNumber = 13
  cutLayer = "V12"
  lowerLayer = "M12"
  upperLayer = "M13"
  upperLayerEncWidth = 0.000
  upperLayerEncHeight = 0.0035
  lowerLayerEncWidth = 0.0035
  lowerLayerEncHeight = 0.000
  cutWidth = 0.3600
  cutHeight = 0.3600
  isDefaultContact = 1
}

PRRule { 
  rowSpacingTopTop = 0.0 
  rowSpacingBotBot = 0.0 
  abuttableTopTop = 1 
  abuttableTopBot = 0 
  abuttableBotBot = 1 
} 

Tile "coresite" { 
  width = 0.045
  height = 0.1440
} 
