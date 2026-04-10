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

            ' Skip already processed mails
            If InStr(Mail.Categories, "Processed") > 0 Then GoTo ContinueLoop
            
            ' Skip mails older than the filter date
            If Mail.SentOn < FilterDate Then GoTo ContinueLoop

            Dim senderSMTP As String
            senderSMTP = LCase(GetSMTP(Mail))

            '==> Match sender + subject
            If InStr(senderSMTP, "No-Reply@FuelsPricing.com") > 0 _
               And InStr(Mail.Subject, "Price Adjustment") > 0 Then
               
                '==> Determine station
                If InStr(Mail.Subject, "NORTH POINT") > 0 Then
                    Station = "NORTH POINT"
                ElseIf InStr(Mail.Subject, "CHAIWAN") > 0 Then
                    Station = "CHAIWAN"
                Else
                    Station = "UNKNOWN"
                End If
                
                '==> Determine date (SentOn + 1)
                SentDate = Mail.SentOn
                PriceDate = DateAdd("d", 1, SentDate)
                
                '==> Extract body text
                BodyText = Mail.Body
                
                '==> Regex setup (unchanged)
                Set RE = CreateObject("VBScript.RegExp")
                RE.Global = True
                RE.IgnoreCase = True
                RE.Multiline = True
                RE.Pattern = "(Synergy[^\r\n]+?)\s+" & _
                             "([\d]+\.[\d]+)\s+" & _
                             "([\d]+\.[\d]+)\s+" & _
                             "((?:[+\-]\s*\d+(?:\.\d+)?)|(?:\d+(?:\.\d+)?)|(?:No\s*Change))"
                
                Set Matches = RE.Execute(BodyText)

                '==> Skip if nothing matched
                If Matches.Count = 0 Then GoTo ContinueLoop
                
                '==> Open or create Excel workbook
                On Error Resume Next
                Set ExcelApp = GetObject(, "Excel.Application")
                If ExcelApp Is Nothing Then Set ExcelApp = CreateObject("Excel.Application")
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
                
                '==> Append each extracted row
                For Each M In Matches
                    LastRow = ws.Cells(ws.Rows.Count, 1).End(-4162).row + 1 'xlUp
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
                
                ' MARK AS PROCESSED
                Mail.Categories = "Processed"
                Mail.Save
                
            End If
        End If
ContinueLoop:
    Next Item
    
    MsgBox "Fuel price data extraction completed!", vbInformation
End Sub


'====================================================================
' UTILITY FUNCTION — UNIVERSAL SMTP ADDRESS (FOR ALL SENDERS)
'====================================================================
Function GetSMTP(M As Outlook.MailItem) As String
    Dim AE As Outlook.AddressEntry
    Dim EU As Outlook.ExchangeUser
    Dim ED As Outlook.ExchangeDistributionList
    
    On Error Resume Next
    Set AE = M.Sender
    
    ' Case 1: SMTP sender (external)
    If M.SenderEmailType = "SMTP" Then
        GetSMTP = M.SenderEmailAddress
        Exit Function
    End If
    
    ' Case 2: EX sender (internal or shared mailbox)
    If Not AE Is Nothing Then
        Set EU = AE.GetExchangeUser
        If Not EU Is Nothing Then
            GetSMTP = EU.PrimarySmtpAddress
            Exit Function
        End If
        
        Set ED = AE.GetExchangeDistributionList
        If Not ED Is Nothing Then
            GetSMTP = ED.PrimarySmtpAddress
            Exit Function
        End If
    End If
    
    ' Fallback
    GetSMTP = M.SenderEmailAddress
    
End Function

