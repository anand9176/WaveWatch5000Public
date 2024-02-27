
import exceptions

import numpy as np
import scipy

thisAlgoProps = {# dont rename this
    'guiName' : 'dominantFrequency',
    'guiName_short' : 'DF',
    'guiColor' : 'slateblue',
    'inputs' : (
        ('', 'electroData'),
        ('WW', 'NonCLChanToProc'),
    ),
}

def compute(data):# dont rename this
            
    electroData, NonCLChanToProc = data
    nbElecs = len(electroData)
    if not nbElecs: raise exceptions.NoElectrodes()
    electroData = electroData[NonCLChanToProc]
    
    #aSeq_col = aSeq.T# transpose prob not necessary in numpy? (as it treats 1d array the same, cf to Matlab)
    hann = np.hanning(len(electroData) + 2)[1:-1]# ^^!! this matches matlab's hanning() ... but that doesnt have 0 weighted fringes, which is what the orig code said the process was doing..so maybe just np.hanning(length(aSeq))?
    aSeq_hannTaperred = electroData*hann# applies Hanning window to taper edges of signal to 0. (CS, see note above about fringe weighting )
    aSeq_hannTaperred = np.abs(aSeq_hannTaperred)# rectify
    
    # Apply 3-15 Hz bandpass filter
    #
    filterOrder = 2# specify order of the filter used (not specified in paper)
    passBand = np.array([3, 15])
    Fs = 2000
    [b, a] = scipy.signal.butter(filterOrder, passBand/(Fs/2), btype = 'bandpass')
    # [w, h] = scipy.signal.freqz(b, a)
    
    # Filter signal using a and b coefficients obtained from the butter (bandpass) filter
    #
    aSeq_filtered = scipy.signal.lfilter(b, a, aSeq_hannTaperred)
    
    # Apply 4096-point FFT (spectral res, 0.24Hz)
    Y = scipy.fft.fft(aSeq_filtered, n = 4096)
    L = len(Y)# == 4096
    
    P2 = np.abs(Y/L)
    # note these numpy slices are views in on same data. Same refs... if you mod here, it'll mod baack there
    P1 = P2[:(int(L/2) + 1)]# CS: is one more than half size of P2.. yeah?
    # MLab: P1(2:end-1) = 2*P1(2:end-1);# FFT spectrum (single sided)
    P1[1:-1] = 2*P1[1:-1]# FFT spectrum (single sided)
    # MLab: f = Fs*(0:(L/2))/L;
    f = Fs*np.arange((L/2) + 1)/L# frequency domain 
    
    # Find frequency with largest magnitude in each spectrum and assign as DF
    # MLab: [~,I] = max(abs(P1));  % finds maximum value of FFT spectrum
    maxVal_idx = np.argmax(np.abs(P1))
    DF = f[maxVal_idx]# finds frequency associated with max value from FFT
    
    return DF
