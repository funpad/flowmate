import wave
import math
import struct
import os

def generate_tone(frequencies, duration=1.5, volume=0.5, sample_rate=44100):
    """Generate a sequence of tones with fading."""
    num_samples = int(sample_rate * duration)
    data = []
    
    # Simple multi-tone sequence
    for i in range(num_samples):
        t = i / sample_rate
        
        # Determine which frequency to play based on time
        idx = int(t / (duration / len(frequencies)))
        idx = min(idx, len(frequencies) - 1)
        freq = frequencies[idx]
        
        # Sine wave
        val = math.sin(2 * math.pi * freq * t)
        
        # Global fade out
        fade = 1.0
        if i > num_samples * 0.7:
            fade = 1.0 - (i - num_samples * 0.7) / (num_samples * 0.3)
            
        # Per-tone fade in/out for smoother transitions
        tone_t = t % (duration / len(frequencies))
        tone_dur = duration / len(frequencies)
        tone_fade = 1.0
        if tone_t < 0.05: tone_fade = tone_t / 0.05
        if tone_t > tone_dur - 0.05: tone_fade = (tone_dur - tone_t) / 0.05
        
        sample = int(val * volume * fade * tone_fade * 32767)
        data.append(struct.pack('<h', sample))
    return b"".join(data)

def save_wav(filename, data, sample_rate=44100):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with wave.open(filename, 'wb') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(data)

if __name__ == "__main__":
    # SUCCESS: C4, E4, G4, C5 rising (Joyful)
    success_tones = [261.63, 329.63, 392.00, 523.25]
    save_wav("assets/success.wav", generate_tone(success_tones, duration=0.8, volume=0.4))
    
    # BREAK END / START TASK: A high clear ding (E5-A5)
    start_tones = [659.25, 880.00]
    save_wav("assets/start_task.wav", generate_tone(start_tones, duration=0.5, volume=0.3))
    
    print("UI Sounds generated in assets/")
