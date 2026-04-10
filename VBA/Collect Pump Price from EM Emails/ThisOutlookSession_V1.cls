VERSION 1.0 CLASS
BEGIN
  MultiUse = -1  'True
END
Attribute VB_Name = "ThisOutlookSession"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = True
Option Explicit

Private Sub Application_NewMailEx(ByVal EntryIDCollection As String)
    On Error Resume Next
    Dim ns As Outlook.NameSpace
    Dim itm As Outlook.MailItem
    Dim mbx As Outlook.Recipient
    Dim Inbox As Outlook.MAPIFolder
    Dim xlFilePath As String
    Dim EntryIDs() As String
    Dim i As Long

    '==> Checkpoint
    Debug.Print "Triggered NewMailEx"
    MsgBox "Triggered NewMailEx"

    ' Split in case multiple mails arrive at once
    EntryIDs = Split(EntryIDCollection, ",")

    Set ns = Application.GetNamespace("MAPI")
    Set mbx = ns.CreateRecipient("celine.wang@feoso.com")
    Set Inbox = ns.GetSharedDefaultFolder(mbx, olFolderInbox)

    For i = LBound(EntryIDs) To UBound(EntryIDs)
        Set itm = ns.GetItemFromID(EntryIDs(i))
        If Not itm Is Nothing Then
            If TypeName(itm) = "MailItem" Then
                If InStr(LCase(itm.Subject), "price adjustment") > 0 Then
                    If InStr(LCase(itm.SenderEmailAddress), "No-Reply@FuelsPricing.com") > 0 Then
                        Call ExtractFuelPrices_Final
                    End If
                End If
            End If
        End If
    Next i
End Sub

Sub ExtractFuelPrices_Final()
    Dim ns As Outlook.NameSpace
    Dim Inbox As Outlook.MAPIFolder
    Dim Item As Object
    Dim Mail As Outlook.MailItem
    Dim ExcelApp As Object
    Dim wb As Object
    Dim ws As Object
    Dim xlFilePath As String
    
    Dim Station As String
    Dim SentDate As Date
    Dim PriceDate As Date
    Dim BodyText As String
    Dim RE As Object, Matches As Object, M As Object
    Dim LastRow As Long
    Dim FilterDate As Date

    '==> Excel output path
    xlFilePath = "C:\Users\Celine Wang\OneDrive - Rosino-Axle\Desktop\Celine Wang\Petrol Stations\Pump Price\PriceData.xlsx"

    '==> Set the lower bound date for processing
    FilterDate = DateSerial(2025, 11, 4)
    
    Set ns = Application.GetNamespace("MAPI")
    Dim mbx As Outlook.Recipient
    Set mbx = ns.CreateRecipient("celine.wang@feoso.com")
    Set Inbox = ns.GetSharedDefaultFolder(mbx, olFolderInbox)

    '==> Loop through emails in Inbox
    For Each Item In Inbox.Items
        If TypeName(Item) = "MailItem" Then
            Set Mail = Item
            If InStr(Mail.Categories, "Processed") > 0 Then GoTo ContinueLoop
            If Mail.SentOn < FilterDate Then GoTo ContinueLoop

            If InStr(Mail.SenderEmailAddress, "No-Reply@FuelsPricing.com") > 0 _
               And InStr(Mail.Subject, "Price Adjustment") > 0 Then

                '==> Determine station
                If InStr(Mail.Subject, "NORTH POINT") > 0 Then
                    Station = "NORTH POINT"
                ElseIf InStr(Mail.Subject, "CHAIWAN") > 0 Then
                    Station = "CHAIWAN"
                Else
                    Station = "UNKNOWN"
                End If

                SentDate = Mail.SentOn
                PriceDate = DateAdd("d", 1, SentDate)
                BodyText = Mail.Body

                Set RE = CreateObject("VBScript.RegExp")
                RE.Global = True
                RE.IgnoreCase = True
                RE.Multiline = True
                RE.Pattern = "(Synergy[^\r\n]+?)\s+" & _
                             "([\d]+\.[\d]+)\s+" & _
                             "([\d]+\.[\d]+)\s+" & _
                             "((?:[+\-]\s*\d+(?:\.\d+)?)|(?:\d+(?:\.\d+)?)|(?:No\s*Change))"
                Set Matches = RE.Execute(BodyText)

                If Matches.Count = 0 Then GoTo ContinueLoop

                On Error Resume Next
                Set ExcelApp = GetObject(, "Excel.Application")
                If ExcelApp Is Nothing Then
                    Set ExcelApp = CreateObject("Excel.Application")
                End If
                On Error GoTo 0

                ExcelApp.Visible = False

                If Dir(xlFilePath) = "" Then
                    Set wb = ExcelApp.Workbooks.Add
                    Set ws = wb.Sheets(1)
                    ws.Range("A1:F1").Value = Array("Station", "Effective Date", "Product Name", _
                        "Current Price ($/Litre)", "New Price ($/Litre)", "Change ($/Litre)")
                    wb.SaveAs xlFilePath
                Else
                    Set wb = ExcelApp.Workbooks.Open(xlFilePath)
                    Set ws = wb.Sheets(1)
                End If

                For Each M In Matches
                    LastRow = ws.Cells(ws.Rows.Count, 1).End(-4162).row + 1
                    ws.Cells(LastRow, 1).Value = Station
                    ws.Cells(LastRow, 2).Value = Format(PriceDate, "yyyy-mm-dd")
                    ws.Cells(LastRow, 3).Value = Trim(M.SubMatches(0))
                    ws.Cells(LastRow, 4).Value = Trim(M.SubMatches(1))
                    ws.Cells(LastRow, 5).Value = Trim(M.SubMatches(2))
                    Dim changeVal As String
                    changeVal = Trim(M.SubMatches(3))
                    changeVal = Replace(changeVal, " ", "")
                    
                    If LCase(changeVal) = "nochange" Then
                        ws.Cells(LastRow, 6).Value = "No Change"
                    Else
                        ws.Cells(LastRow, 6).Value = CDbl(changeVal)
                    End If
                Next M

                wb.Save
                wb.Close SaveChanges:=True
                ExcelApp.Quit

                Mail.Categories = "Processed"
                Mail.Save
            End If
        End If
ContinueLoop:
    Next Item

    '==> Checkpoint
    MsgBox "Macro finished!", vbInformation
End Sub






