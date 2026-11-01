param(
 [string]$PayloadFile='',
 [ValidateRange(1,120)][int]$DeadlineSeconds=15,
 [string]$SelfTestTarget='',
 [string]$SelfTestProcess='',
 [string]$SelfTestProgram=''
)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class PasteWindow {
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr handle);
 [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr handle, int command);
}
"@
$claudeProgram=''
$appName='GPT 桌面'
function Finish($ok,$reason){
 @{ok=$ok;reason=$reason;send_dispatched=$false}|ConvertTo-Json -Compress
 exit
}
function Get-TextKey($text){
 $flat=([string]$text) -replace '\s+',''
 $sha=[Security.Cryptography.SHA256]::Create()
 return ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($flat)))) -replace '-',''
}
function Read-PastedKeys($file){
 if(!$file -or !(Test-Path -LiteralPath $file)){return @()}
 return @(Get-Content -LiteralPath $file -Encoding UTF8 -ErrorAction SilentlyContinue|Where-Object {$_})
}
function Save-PastedKey($file,$key){
 if(!$file){return}
 try{
  $keys=@(Read-PastedKeys $file)+$key|Select-Object -Last 20
  [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($file))
  [IO.File]::WriteAllLines($file,[string[]]$keys,[Text.UTF8Encoding]::new($false))
 }catch{}
}
function Test-CodexProcess($process){
 if(!$process){return $false}
 $path=[string]$process.Path
 if($process.ProcessName -eq 'ChatGPT'){
  return $path -match '(?i)[\\/]WindowsApps[\\/]OpenAI\.Codex_[^\\/]+[\\/]app[\\/]ChatGPT\.exe$'
 }
 return $process.ProcessName -eq 'Codex' -and $path -match '(?i)[\\/]Codex(?:[\\/]|\.exe$)'
}
function Test-TargetMatch($processName,$actualPath,$expectedProgram){
 if(!$expectedProgram -or !$processName -or !$actualPath){return $false}
 $expected=[IO.Path]::GetFullPath([string]$expectedProgram)
 $expectedName=[IO.Path]::GetFileNameWithoutExtension($expected)
 if($processName -ine $expectedName){return $false}
 $actual=[string]$actualPath
 if($actual -ieq $expected){return $true}
 # 根目录启动器可转交同安装目录内的版本化程序（如 app-1.15.0/Gemini.exe、app-*/Claude.exe）。
 $root=[IO.Path]::GetDirectoryName($expected)
 $expectedFile=[IO.Path]::GetFileName($expected)
 return $actual -match ('(?i)^'+[regex]::Escape($root)+'[\\/](?:app-[^\\/]+[\\/])?'+[regex]::Escape($expectedFile)+'$')
}
function Test-TargetProcess($process){
 if(!$claudeProgram){return Test-CodexProcess $process}
 if(!$process){return $false}
 $actual=''
 try{$actual=[string]$process.Path}catch{$actual=''}
 return Test-TargetMatch $process.ProcessName $actual $claudeProgram
}

if($SelfTestTarget){
 @{match=(Test-TargetMatch $SelfTestProcess $SelfTestTarget $SelfTestProgram)}|ConvertTo-Json -Compress
 exit
}

$payload=[IO.File]::ReadAllText($PayloadFile,[Text.Encoding]::UTF8)|ConvertFrom-Json
$prompt=[string]$payload.prompt
$claudeProgram=[string]$payload.program
$traceFile=if($payload.trace_file){[string]$payload.trace_file}else{''}
$ownDraft=$false
$attachment=if($payload.attachment){[string]$payload.attachment}else{''}
$appName=if($payload.app_name){[string]$payload.app_name}elseif($claudeProgram){'Claude Desktop'}else{'GPT 桌面'}
if($null -ne $payload.deadline){$DeadlineSeconds=[Math]::Min(120,[Math]::Max(1,[int]$payload.deadline))}

try{
 $deadline=[DateTime]::UtcNow.AddSeconds($DeadlineSeconds)
 while([DateTime]::UtcNow -lt $deadline){
  Start-Sleep -Milliseconds 450
  $windows=@(Get-Process -ErrorAction SilentlyContinue|Where-Object { $_.MainWindowHandle -ne 0 -and (Test-TargetProcess $_) })
  $foreground=[PasteWindow]::GetForegroundWindow()
  $process=$windows|Where-Object {$_.MainWindowHandle -eq $foreground}|Select-Object -First 1
  if(!$process -and $windows.Count -eq 1){$process=$windows[0]}
  if(!$process){continue}
  $handle=$process.MainWindowHandle
  $window=[System.Windows.Automation.AutomationElement]::FromHandle($handle)
  $condition=[System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::Edit)
  $edits=@($window.FindAll([System.Windows.Automation.TreeScope]::Descendants,$condition)|Where-Object {
   !$_.Current.IsOffscreen -and $_.Current.IsEnabled -and $_.Current.IsKeyboardFocusable -and !$_.Current.IsPassword
  })
  # Prefer the large message composer, without depending on localized labels or task headers.
  $edit=$edits|Sort-Object { $_.Current.BoundingRectangle.Width * $_.Current.BoundingRectangle.Height } -Descending|Select-Object -First 1
  if(!$edit){continue}
  if($claudeProgram){
   # 桌面程序的草稿不能被覆盖；无法读取输入内容时也不冒险全选替换。
   $valuePattern=$null;$textPattern=$null;$content=$null
   if($edit.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern,[ref]$valuePattern)){
    $content=$valuePattern.Current.Value
   }elseif($edit.TryGetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern,[ref]$textPattern)){
    $content=$textPattern.DocumentRange.GetText(-1)
   }
   if($null -eq $content){continue}
   if($content.Trim()){
    if($content.Trim() -eq $prompt.Trim()){
     $same=if($appName -eq 'Claude Desktop'){'Claude Desktop 输入框已有本次任务路径，请手动发送。'}else{"$appName 输入框已有本次任务内容，请手动发送。"}
     Finish $true $same
    }
    # 上一次由本助手粘进去、用户没发送的任务（续用上次对话时最常见）不算用户草稿，允许替换；
    # 用户手写或改过的内容仍然不覆盖。
    if(@(Read-PastedKeys $traceFile) -contains (Get-TextKey $content)){$ownDraft=$true}
    else{
     $draft=if($appName -eq 'Claude Desktop'){'Claude Desktop 输入框已有草稿，未覆盖；任务路径已复制，请自行粘贴并手动发送。'}else{"$appName 输入框已有草稿，未覆盖；任务已复制到剪贴板，请自行粘贴并手动发送。"}
     Finish $false $draft
    }
   }
  }
  [void][PasteWindow]::ShowWindowAsync($handle,9)
  [void][PasteWindow]::SetForegroundWindow($handle)
  $edit.SetFocus()
  Start-Sleep -Milliseconds 200
  if([PasteWindow]::GetForegroundWindow() -ne $handle -or !$edit.Current.HasKeyboardFocus){continue}
  if($ownDraft){
   # 先清掉上次遗留的旧任务，再贴附件，避免全选把刚贴上的附件一起替换掉。
   [System.Windows.Forms.SendKeys]::SendWait('^a')
   [System.Windows.Forms.SendKeys]::SendWait('{DELETE}')
   Start-Sleep -Milliseconds 200
  }
  if($attachment){
   # 长任务（REQ-S01-70）：先以文件形式粘贴任务文件作附件，等上传后再粘贴短指令。
   $files=New-Object System.Collections.Specialized.StringCollection
   [void]$files.Add($attachment)
   [System.Windows.Forms.Clipboard]::SetFileDropList($files)
   [System.Windows.Forms.SendKeys]::SendWait('^v')
   Start-Sleep -Milliseconds 1500
  }
  [System.Windows.Forms.Clipboard]::SetText($prompt)
  if(!$claudeProgram){[System.Windows.Forms.SendKeys]::SendWait('^a')}
  [System.Windows.Forms.SendKeys]::SendWait('^v')
  Save-PastedKey $traceFile (Get-TextKey $prompt)
  if($attachment){Finish $true "已把任务文件作为附件、短指令粘贴到 $appName；请确认附件已出现再手动发送，没有出现就把 $attachment 拖进对话框。"}
  Finish $true "已粘贴到 $appName，请检查内容并手动点击发送。"
 }
 Finish $false "已复制到剪贴板；未能自动粘贴，请在 $appName 输入框中手动粘贴并发送。"
}catch{
 Finish $false "自动粘贴未完成；任务已复制到剪贴板，请在 $appName 输入框中手动粘贴并发送。"
}
