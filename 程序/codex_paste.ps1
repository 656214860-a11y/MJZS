param([Parameter(Mandatory=$true)][string]$PayloadFile)
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
$title=[string]$payload.title
$prompt=[string]$payload.prompt
$draft=[string]$payload.draft
$project=[string]$payload.project
$newTask=$draft.Length -gt 0
$diagnostic=[bool]$payload.diagnostic
$autoSend=[bool]$payload.auto_send
$confirmation=$payload.confirmation
$script:sendDispatched=$false;$script:pasteDispatched=$false;$script:promptVerified=$false
function Test-CodexProcess($process){
 if(!$process){return $false}
 $path=[string]$process.Path
 if($process.ProcessName -eq 'ChatGPT'){
  return $path -match '(?i)[\\/]WindowsApps[\\/]OpenAI\.Codex_[^\\/]+[\\/]app[\\/]ChatGPT\.exe$'
 }
 return $process.ProcessName -eq 'Codex' -and $path -match '(?i)[\\/]Codex(?:[\\/]|\.exe$)'
}
function Text-Hash($value){
 $sha=[Security.Cryptography.SHA256]::Create()
 try{return [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes((Normalize-Text $value)))).Replace('-','').ToLowerInvariant()}finally{$sha.Dispose()}
}
function Test-SendContent($edit){
 $value=Read-Edit $edit
 if($null -eq $value){return $false}
 if($confirmation){
  return $value.Length -gt 0 -and (Text-Hash $value) -eq $confirmation.text_sha256 -and (($edit.GetRuntimeId()) -join ':') -eq $confirmation.editor_id
 }
 return $value -eq (Normalize-Text $prompt)
}
function Finish($ok,$reason){
 $outcome=@{ok=$ok;reason=$reason;send_dispatched=[bool]$script:sendDispatched}
 # Offer confirmation only after this task was pasted/verified and no Send
 # click was dispatched. Bind approval to this editor and this exact snapshot.
 if(!$confirmation -and !$script:sendDispatched -and ($script:pasteDispatched -or $script:promptVerified)){
  try{
   $value=Read-Edit $edit
   if($null -ne $value -and $value.Length -gt 0){
    $outcome.can_confirm=$true
    $outcome.confirmation=@{handle=[long]$handle;editor_id=(($edit.GetRuntimeId()) -join ':');text_sha256=(Text-Hash $value)}
   }
  }catch{}
 }
 $outcome|ConvertTo-Json -Depth 4 -Compress;exit
}
function Normalize-Text($value){
 if($null -eq $value){return $null}
 return ([string]$value).Replace("`r`n","`n").Replace("`r","`n").Replace([string][char]0x200B,'').Replace([string][char]0xFEFF,'').Trim()
}
function Composer-Value($value,$name,$class){
 if($null -eq $value){return $null}
 $text=Normalize-Text $value
 # Chromium exposes this CSS placeholder as a leading blank line plus its
 # accessible label. It is not a user draft. Keep real typed text intact.
 if($class -match '\bProseMirror\b' -and [string]$value -match '^\s*\r?\n' -and
    $name -match '^(使用 ChatGPT Work|Ask anything|Message Codex|向 Codex 提问)$' -and
    $text -eq (Normalize-Text $name)){return ''}
 return $text
}
function Read-Edit($node){
 $pattern=$null
 if($node.TryGetCurrentPattern([Windows.Automation.ValuePattern]::Pattern,[ref]$pattern)){
  if($pattern.Current.IsReadOnly){return $null}
  return Composer-Value ([string]$pattern.Current.Value) $node.Current.Name $node.Current.ClassName
 }
 if($node.TryGetCurrentPattern([Windows.Automation.TextPattern]::Pattern,[ref]$pattern)){
  return Composer-Value ([string]$pattern.DocumentRange.GetText(-1)) $node.Current.Name $node.Current.ClassName
 }
 return $null
}
function Test-EditorFocus($edit){
 $node=[Windows.Automation.AutomationElement]::FocusedElement
 for($depth=0;$depth -lt 8 -and $null -ne $node;$depth++){
  if([Windows.Automation.Automation]::Compare($node,$edit)){return $true}
  $node=[Windows.Automation.TreeWalker]::ControlViewWalker.GetParent($node)
 }
 return $false
}
function Complete-Task($window,$edit,$handle){
 if(!$autoSend){Finish $true '已自动粘贴到 Codex 输入框。'}
 # Match only the nearby composer Send control. Never use Enter as a fallback,
 # and never click twice when submission acknowledgement is delayed.
 $condition=[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Button)
 for($attempt=0;$attempt -lt 16;$attempt++){
  if([PasteWindow]::GetForegroundWindow() -ne $handle){Finish $false '窗口已切换，本次内容已填入，尚未自动发送。'}
  $value=Read-Edit $edit
  if(!(Test-SendContent $edit)){Finish $false '输入框内容已变化，未自动发送，请检查当前任务。'}
  $target=Target-Window
  if($null -eq $target -or [IntPtr]$target.Current.NativeWindowHandle -ne $handle){Finish $false '当前对话已变化，未自动发送。'}
  $rect=$edit.Current.BoundingRectangle;$buttons=@()
  foreach($button in $window.FindAll([Windows.Automation.TreeScope]::Descendants,$condition)){
   $c=$button.Current;$b=$c.BoundingRectangle
   if($c.IsOffscreen -or !$c.IsEnabled -or $c.Name -notmatch '^(发送|发送消息|Send|Send message)(\s*\([^)]*\))?$'){continue}
   if($b.Top -lt $rect.Top -or $b.Top -gt ($rect.Bottom+110) -or $b.Left -lt $rect.Left -or $b.Right -gt ($rect.Right+40)){continue}
   $buttons+=,$button
  }
  if($buttons.Count -eq 1){
   $invoke=$null
   if($buttons[0].TryGetCurrentPattern([Windows.Automation.InvokePattern]::Pattern,[ref]$invoke)){
    if(!(Test-SendContent $edit) -or [PasteWindow]::GetForegroundWindow() -ne $handle){Finish $false '输入框或焦点已变化，未自动发送。'}
    $script:sendDispatched=$true
    $invoke.Invoke()
    for($wait=0;$wait -lt 16;$wait++){
     Start-Sleep -Milliseconds 250
     try{$remaining=Read-Edit $edit;if($null -ne $remaining -and $remaining.Length -eq 0){Finish $true '已自动粘贴并点击发送，输入框已清空。'}}catch{}
    }
    Finish $false '已点击发送，尚未确认提交结果；请查看 Codex，未重复发送。'
   }
  }
  Start-Sleep -Milliseconds 250
 }
 Finish $false '本次内容已填入，发送按钮暂不可用；请查看 Codex。'
}
function Target-Window{
 $windows=[Windows.Automation.AutomationElement]::RootElement.FindAll([Windows.Automation.TreeScope]::Children,[Windows.Automation.Condition]::TrueCondition)
 foreach($candidate in $windows){
  try{
   $process=Get-Process -Id $candidate.Current.ProcessId -ErrorAction SilentlyContinue
   if(!(Test-CodexProcess $process)){continue}
   if($confirmation -and [long]$candidate.Current.NativeWindowHandle -eq $confirmation.handle){return $candidate}
   $condition=[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty,$title)
   $headers=$candidate.FindAll([Windows.Automation.TreeScope]::Descendants,$condition)
   foreach($header in $headers){if(!$header.Current.IsOffscreen -and $header.Current.BoundingRectangle.Top -lt ($candidate.Current.BoundingRectangle.Top+120)){return $candidate}}
   if($newTask){
    $editCondition=[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Edit)
    foreach($node in $candidate.FindAll([Windows.Automation.TreeScope]::Descendants,$editCondition)){
     $value=Read-Edit $node
     if(!$node.Current.IsOffscreen -and $null -ne $value -and ($value.Trim() -eq $draft.Trim() -or $value.Trim() -eq $prompt.Trim())){return $candidate}
    }
   }
  }catch{}
 }
 return $null
}
try {
 $deadline=[DateTime]::UtcNow.AddSeconds(15)
 $stable=0;$lastHandle=[IntPtr]::Zero
 while([DateTime]::UtcNow -lt $deadline){
  Start-Sleep -Milliseconds 450
  $window=Target-Window
  if($null -eq $window){continue}
  $handle=[IntPtr]$window.Current.NativeWindowHandle
  if($handle -eq [IntPtr]::Zero){continue}
  $process=Get-Process -Id $window.Current.ProcessId -ErrorAction SilentlyContinue
  if(!(Test-CodexProcess $process)){$stable=0;continue}
  $titleCondition=[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty,$title)
  $titleNodes=$window.FindAll([Windows.Automation.TreeScope]::Descendants,$titleCondition)
  $headerFound=$false
  foreach($titleNode in $titleNodes){
   $tc=$titleNode.Current
   if(!$tc.IsOffscreen -and $tc.BoundingRectangle.Top -lt ($window.Current.BoundingRectangle.Top+120)){$headerFound=$true;break}
  }
  # A newly opened task has not received its final title yet. Its unique task-file
  # draft identifies the target composer below; an empty draft also needs the new
  # task heading and the intended project visible in the same window.
  if(!$headerFound -and !$newTask){$stable=0;continue}
  if($handle -eq $lastHandle){$stable++}else{$stable=1;$lastHandle=$handle}
  if($stable -lt 3){continue}
  $condition=[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Edit)
  $nodes=$window.FindAll([Windows.Automation.TreeScope]::Descendants,$condition)
  $candidates=@()
  foreach($node in $nodes){
   $c=$node.Current;$rect=$c.BoundingRectangle;$area=$window.Current.BoundingRectangle
   if($c.IsOffscreen -or !$c.IsEnabled -or !$c.IsKeyboardFocusable){continue}
   # Require the message composer accessibility label; never guess a search box.
   if($c.Name -notmatch '(?i)(message|prompt|ask|follow.?up|向.*提问|发送消息|输入消息|输入.*提示|后续|询问|提问|使用 ChatGPT Work)'){continue}
   # New-task composers can be centered before the first message is sent.
   $minimumTop=if($newTask){0.15}else{0.4}
   if($rect.Top -lt ($area.Top+$area.Height*$minimumTop)){continue}
   $candidates+=,$node
  }
  if($candidates.Count -ne 1){continue}
  $edit=$candidates[0];$before=Read-Edit $edit
  if($null -eq $before){continue}
  $matchesDraft=$newTask -and $before.Replace("`r`n","`n").Trim() -eq $draft.Replace("`r`n","`n").Trim()
  $matchesPrompt=$before.Replace("`r`n","`n").Trim() -eq $prompt.Replace("`r`n","`n").Trim()
  $script:promptVerified=$matchesPrompt
  if($confirmation -and ([long]$handle -ne $confirmation.handle -or !(Test-SendContent $edit))){Finish $false '确认后输入框内容或对话已变化，未发送。请重新检查当前任务。'}
  if(!$confirmation -and $newTask -and !$headerFound -and !$matchesDraft -and !$matchesPrompt){
   $newHeader=$false;$projectFound=$false
   $elements=$window.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.Condition]::TrueCondition)
   foreach($element in $elements){
    $ec=$element.Current
    if($ec.IsOffscreen){continue}
    if($ec.Name -match '^(New task|New thread|新任务|新建任务|新对话)$' -and $ec.BoundingRectangle.Top -lt ($window.Current.BoundingRectangle.Top+160)){$newHeader=$true}
    if($project -and ($ec.Name -eq $project -or $ec.Name -eq [IO.Path]::GetFileName($project) -or $ec.Name -eq ('项目：'+[IO.Path]::GetFileName($project)))){$projectFound=$true}
   }
   if(!$newHeader -or !$projectFound){continue}
  }
  if($diagnostic){Finish $true ('已定位当前任务的输入框；正文长度：'+$before.Length+'；诊断未执行粘贴或发送。')}
  if(!$confirmation -and $before.Trim().Length -gt 0 -and !$matchesDraft -and !$matchesPrompt){Finish $false 'Codex 输入框已有草稿，已保留；本次内容在剪贴板中。'}
  if([PasteWindow]::GetForegroundWindow() -ne $handle){
   [void][PasteWindow]::ShowWindowAsync($handle,9)
   [void][PasteWindow]::SetForegroundWindow($handle)
   Start-Sleep -Milliseconds 250
  }
  $edit.SetFocus();$focusReady=$false
  for($focusWait=0;$focusWait -lt 8;$focusWait++){
   Start-Sleep -Milliseconds 150
   if([PasteWindow]::GetForegroundWindow() -eq $handle -and (Test-EditorFocus $edit)){$focusReady=$true;break}
  }
  # A newly opened composer may focus its child paragraph after a short delay.
  # Retarget only before dispatching input; never repeat a dispatched paste.
  if(!$focusReady){$stable=0;continue}
  if((Read-Edit $edit) -ne $before){Finish $false '输入框内容已变化，已保留；本次内容仍在剪贴板中。'}
  if($confirmation){Complete-Task $window $edit $handle}
  if($matchesPrompt){Complete-Task $window $edit $handle}
  # Use the immutable invocation payload, even if the user copied something
  # else while the task window was opening. Never submit clipboard contents.
  [Windows.Forms.Clipboard]::SetText($prompt)
  if([PasteWindow]::GetForegroundWindow() -ne $handle -or !(Test-EditorFocus $edit)){Finish $false '焦点已变化，任务已保留，请重新点击 Agent。'}
  # Only replace the exact file-link draft inserted by this invocation.
  if($matchesDraft){[Windows.Forms.SendKeys]::SendWait('^a')}
  $script:pasteDispatched=$true
  [Windows.Forms.SendKeys]::SendWait('^v')
  # Never retry paste after dispatch: a slow composer must not receive duplicates.
  for($i=0;$i -lt 8;$i++){
   Start-Sleep -Milliseconds 250
   $after=Read-Edit $edit
   if($null -ne $after -and $after -eq (Normalize-Text $prompt)){
    Complete-Task $window $edit $handle
   }
  }
  Finish $false '已尝试粘贴，请检查 Codex 输入框；为避免重复，未再次粘贴。'
 }
 Finish $false '未找到可确认的 Codex 消息输入框；本次内容已复制，可手动粘贴。'
}catch{
 if($script:sendDispatched){Finish $false '已尝试点击发送，结果未确认；请检查 Codex，未重复发送。'}
 Finish $false '自动粘贴或发送未完成，请检查 Codex 输入框；本次内容仍在剪贴板中。'
}
