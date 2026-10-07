Add-Type -AssemblyName System.Speech

$samples = @{
    "caregiver_memo.wav" = "Dad loves jazz. His grandson is named Leo. Avoid talking about driving. I'm dropping off groceries at 4 PM today."
    "senior_jazz.wav" = "Hi, how's it going today? I've been listening to a lot of Miles Davis lately, I love him."
    "senior_distress.wav" = "I fell down earlier and I'm scared."
    "senior_grandson.wav" = "I forgot, what is my grandson's name?"
    "senior_schedule.wav" = "Hi there. Is anyone coming by today?"
}

$sampleDir = Split-Path -Parent $MyInvocation.MyCommand.Path

foreach ($file in $samples.Keys) {
    $outPath = Join-Path $sampleDir $file
    Write-Host "Synthesizing $file..."
    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $synth.Rate = -1
    $synth.SetOutputToWaveFile($outPath)
    $synth.Speak($samples[$file])
    $synth.Dispose()
    $size = (Get-Item $outPath).Length
    Write-Host "  Generated $file ($size bytes)"
}

Write-Host "All audio sample files generated successfully!"
