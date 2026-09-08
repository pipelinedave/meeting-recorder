using System;
using System.IO;
using System.Threading;
using CSCore;
using CSCore.Codecs.WAV;
using CSCore.CoreAudioAPI;
using CSCore.SoundIn;
using CSCore.Streams;

public class MeetingAudioRecorder
{
    private WasapiCapture _micCapture;
    private WasapiLoopbackCapture _loopbackCapture;
    private IWaveSource _micSource;
    private IWaveSource _loopbackSource;
    private WaveWriter _writer;
    private bool _recording = false;
    private Thread _recordThread;

    public void Start(string outputPath, string micDeviceName = null, string loopbackDeviceName = null)
    {
        MMDevice micDevice = null;
        MMDevice loopbackDevice = null;

        if (!string.IsNullOrEmpty(micDeviceName))
        {
            var captureDevices = MMDeviceEnumerator.EnumerateDevices(DataFlow.Capture, DeviceState.Active);
            foreach (var dev in captureDevices)
            {
                if (dev.FriendlyName.IndexOf(micDeviceName, StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    micDevice = dev;
                    break;
                }
            }
        }
        if (micDevice == null)
            micDevice = MMDeviceEnumerator.DefaultAudioEndpoint(DataFlow.Capture, Role.Communications);

        if (!string.IsNullOrEmpty(loopbackDeviceName))
        {
            var renderDevices = MMDeviceEnumerator.EnumerateDevices(DataFlow.Render, DeviceState.Active);
            foreach (var dev in renderDevices)
            {
                if (dev.FriendlyName.IndexOf(loopbackDeviceName, StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    loopbackDevice = dev;
                    break;
                }
            }
        }
        if (loopbackDevice == null)
            loopbackDevice = MMDeviceEnumerator.DefaultAudioEndpoint(DataFlow.Render, Role.Multimedia);

        Console.WriteLine("[*] Mic Device: " + micDevice.FriendlyName);
        Console.WriteLine("[*] System Loopback Device: " + loopbackDevice.FriendlyName);

        // Mute-Status prüfen
        try
        {
            var vol = AudioEndpointVolume.FromDevice(micDevice);
            if (vol.IsMuted)
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine("[!] WARNUNG: Dein Headset-Mikrofon ist in Windows auf STUMMGESCHALTET (Muted)!");
                Console.WriteLine("[*] Versuche automatisches Entstummen (Unmute)...");
                vol.IsMuted = false;
                if (!vol.IsMuted)
                {
                    Console.ForegroundColor = ConsoleColor.Green;
                    Console.WriteLine("[✓] Mikrofon erfolgreich entstummt.");
                }
                else
                {
                    Console.WriteLine("[!] Bitte pruefe die Hardware-Mute-Taste an deinem Poly Headset!");
                }
                Console.ResetColor();
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine("[*] Konnte Mute-Status nicht abfragen: " + ex.Message);
        }

        int targetSampleRate = 16000;

        _micCapture = new WasapiCapture() { Device = micDevice };
        _micCapture.Initialize();

        _loopbackCapture = new WasapiLoopbackCapture() { Device = loopbackDevice };
        _loopbackCapture.Initialize();

        // Native WASAPI liefert meist 48kHz IEEE Float. 
        // Wir wandeln sauber via CSCore FluentExtensions in 16kHz 16-Bit PCM Mono um!
        var rawMic = new SoundInSource(_micCapture);
        _micSource = rawMic.ChangeSampleRate(targetSampleRate).ToMono().ToSampleSource().ToWaveSource(16);

        var rawLoop = new SoundInSource(_loopbackCapture);
        _loopbackSource = rawLoop.ChangeSampleRate(targetSampleRate).ToMono().ToSampleSource().ToWaveSource(16);

        var outputFormat = new WaveFormat(targetSampleRate, 16, 2);
        _writer = new WaveWriter(outputPath, outputFormat);

        _recording = true;
        _micCapture.Start();
        _loopbackCapture.Start();

        _recordThread = new Thread(RecordLoop);
        _recordThread.Start();
        Console.WriteLine("[✓] Dual-Track Aufnahme gestartet: Links=David (Mic), Rechts=Gegenseite (Teams/Sound)");
    }

    private void RecordLoop()
    {
        byte[] micBuffer = new byte[3200];
        byte[] loopBuffer = new byte[3200];
        byte[] stereoBuffer = new byte[6400];

        while (_recording)
        {
            int micRead = _micSource.Read(micBuffer, 0, micBuffer.Length);
            int loopRead = _loopbackSource.Read(loopBuffer, 0, loopBuffer.Length);

            int maxRead = Math.Max(micRead, loopRead);
            if (maxRead > 0)
            {
                int sampleCount = maxRead / 2;
                int outIndex = 0;

                for (int i = 0; i < sampleCount; i++)
                {
                    short micSample = 0;
                    short loopSample = 0;

                    if (i * 2 + 1 < micRead)
                        micSample = (short)(micBuffer[i * 2] | (micBuffer[i * 2 + 1] << 8));

                    if (i * 2 + 1 < loopRead)
                        loopSample = (short)(loopBuffer[i * 2] | (loopBuffer[i * 2 + 1] << 8));

                    // Left channel = David (16-bit PCM)
                    stereoBuffer[outIndex++] = (byte)(micSample & 0xFF);
                    stereoBuffer[outIndex++] = (byte)((micSample >> 8) & 0xFF);

                    // Right channel = Gegenseite (16-bit PCM)
                    stereoBuffer[outIndex++] = (byte)(loopSample & 0xFF);
                    stereoBuffer[outIndex++] = (byte)((loopSample >> 8) & 0xFF);
                }

                _writer.Write(stereoBuffer, 0, outIndex);
            }
            else
            {
                Thread.Sleep(10);
            }
        }
    }

    public void Stop()
    {
        _recording = false;
        if (_recordThread != null && _recordThread.IsAlive)
            _recordThread.Join(2000);

        if (_micCapture != null)
        {
            _micCapture.Stop();
            _micCapture.Dispose();
        }
        if (_loopbackCapture != null)
        {
            _loopbackCapture.Stop();
            _loopbackCapture.Dispose();
        }
        if (_writer != null)
        {
            _writer.Dispose();
        }
        Console.WriteLine("[✓] Aufnahme gestoppt und Stereo-WAV geschrieben.");
    }
}
