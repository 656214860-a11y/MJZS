param([Parameter(Mandatory=$true)][string]$PayloadFile,[ValidateRange(1,120)][int]$DeadlineSeconds=15)
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
$payload=[IO.File]::ReadAllText($PayloadFile,[Text.Encoding]::UTF8)|ConvertFrom-Json
$prompt=[string]$payload.prompt
$claudeProgram=[string]$payload.program
$appName=if($claudeProgram){'Claude Desktop'}else{'GPT 桌面'}
if($null -ne $payload.deadline){$DeadlineSeconds=[Math]::Min(120,[Math]::Max(1,[int]$payload.deadline))}
function Finish($ok,$reason){
 @{ok=$ok;reason=$reason;send_dispatched=$false}|ConvertTo-Json -Compress
 exit
}
function Test-CodexProcess($process){
 if(!$process){return $false}
 $path=[string]$process.Path
 if($process.ProcessName -eq 'ChatGPT'){
  return $path -match '(?i)[\\/]WindowsApps[\\/]OpenAI\.Codex_[^\\/]+[\\/]app[\\/]ChatGPT\.exe$'
 }
 return $process.ProcessName -eq 'Codex' -and $path -match '(?i)[\\/]Codex(?:[\\/]|\.exe$)'
}
function Test-TargetProcess($process){
 if(!$claudeProgram){return Test-CodexProcess $process}
 if(!$process -or $process.ProcessName -ne 'Claude'){return $false}
 $actual=[string]$process.Path
 if(!$actual){return $false}
 $expected=[IO.Path]::GetFullPath($claudeProgram)
 if($actual -ieq $expected){return $true}
 # Squirrel 的根目录启动器可转交同安装目录内的版本化 Claude.exe。
 $root=[IO.Path]::GetDirectoryName($expected)
 return $actual -match ('(?i)^'+[regex]::Escape($root)+'[\\/]app-[^\\/]+[\\/]Claude\.exe$')
}

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
   # Claude 草稿不能被覆盖；无法读取输入内容时也不冒险全选替换。
   $valuePattern=$null;$textPattern=$null;$content=$null
   if($edit.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern,[ref]$valuePattern)){
    $content=$valuePattern.Current.Value
   }elseif($edit.TryGetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern,[ref]$textPattern)){
    $content=$textPattern.DocumentRange.GetText(-1)
   }
   if($null -eq $content){continue}
   if($content.Trim()){
    if($content.Trim() -eq $prompt.Trim()){Finish $true 'Claude Desktop 输入框已有本次任务路径，请手动发送。'}
    Finish $false 'Claude Desktop 输入框已有草稿，未覆盖；任务路径已复制，请自行粘贴并手动发送。'
   }
  }
  [void][PasteWindow]::ShowWindowAsync($handle,9)
  [void][PasteWindow]::SetForegroundWindow($handle)
  $edit.SetFocus()
  Start-Sleep -Milliseconds 200
  if([PasteWindow]::GetForegroundWindow() -ne $handle -or !$edit.Current.HasKeyboardFocus){continue}
  [System.Windows.Forms.Clipboard]::SetText($prompt)
  if(!$claudeProgram){[System.Windows.Forms.SendKeys]::SendWait('^a')}
  [System.Windows.Forms.SendKeys]::SendWait('^v')
  Finish $true "已粘贴到 $appName，请检查内容并手动点击发送。"
 }
 Finish $false "已复制任务内容；未能自动粘贴，请在 $appName 输入框中粘贴并手动发送。"
}catch{
 Finish $false "自动粘贴未完成，内容已复制；请在 $appName 输入框中粘贴并手动发送。"
}
