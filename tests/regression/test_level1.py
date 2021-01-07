import pytest
import warnings
import os
import sys
import shutil
from dotenv import load_dotenv

from kpfpipe.models.level1 import *

# Load .env file for test path 
load_dotenv()

# =============================================================================
# IO
fpath = os.environ['KPFPIPE_TEST_DATA'] + '/NEIDdata/TAUCETI_20191217/L1'
flist = [f for f in os.listdir(fpath)]

def test_from_NEID():
    '''
    Read all available level 0 data and check for data
    '''
    for f in flist:
        data = KPF1.from_fits(os.path.join(fpath, f), 'NEID')

def test_NEID2KPF():
    '''
    Check that data 
    '''
    # Make a temporary folder
    try:
        os.mkdir('temp')
    except FileExistsError:
        pass

    for f in flist:
        # read NEID data and convert to KPF data
        data = KPF1.from_fits(os.path.join(fpath, f), 'NEID')
        to_path = 'temp/' + f
        data.to_fits(to_path)
        # read the converted data
        data2 = KPF1.from_fits(to_path, 'KPF')
        # compare the data value of the two
        for key, value in data2.data.items():
            if value is None:
                assert(data2.data[key] is None)
            else:
                assert(np.all(value == data.data[key]))

    # Clean up 
    shutil.rmtree('temp')

def test_io_exception():

    data = KPF1()
    with pytest.raises(FileNotFoundError):
        # file does not exist 
        data.read('not_exist.fits', 'NEID')

    with pytest.raises(IOError):
        # valid path, but no .fits extension
        path = os.path.join(fpath, flist[0])
        path = path.split('.')[0] # remove the '.fit' from extension
        data.read(path, 'NEID')
    
    data = KPF1()
    path = os.path.join(fpath, flist[0])
    data.read(path, 'NEID')

    with pytest.raises(IOError):
        #trying to overwrite existing data
        data.read(path, 'NEID')


# =============================================================================
# Segments

def test_add_segments():
    '''
    Check that segments are added properly
    '''
    data = KPF1()
    data = KPF1.from_fits(os.path.join(fpath, flist[0]), 'NEID')
    # check that default segments are working
    for fiber, value in data.segments.items():
        if len(value) != 0:
            assert(len(value) == data.data[fiber].shape[1])

    data.add_segment('SCI1', (0, 1), (0, 5), label='test')
    data.add_segment('SCI1', (0, 1), (0 ,5))
    assert('Custom segment 1' in list(data.segments['SCI1']['Label']))
    assert('test' in list(data.segments['SCI1']['Label']))

def test_remove_segment():
    '''
    Check that segments are removed properly
    '''
    data = KPF1()
    data = KPF1.from_fits(os.path.join(fpath, flist[0]), 'NEID')
    data.clear_segment()
    for key, value in data.segments.items():
        assert(len(value) == 0)
    data.add_segment('SCI1', (0, 1), (0, 5), label='test')
    data.add_segment('SCI1', (0, 1), (0 ,5))
    data.remove_segment('SCI1', 'test')
    data.remove_segment('SCI1', 'Custom segment 1')
    assert(len(data.segments['SCI1']) == 0)

def test_segments_exceptions():
    '''
    Check that proper exceptions are raised with an invalid input
    '''
    data = KPF1()
    with pytest.raises(ValueError):
        # adding segment to an empty data
        data.add_segment('SCI1', (0, 1), (0, 2), label='test')
    
    data = KPF1.from_fits(os.path.join(fpath, flist[0]), 'NEID')
    data.add_segment('SCI1', (0, 1), (0, 2), label='test')
    with pytest.raises(ValueError):
        # end index is less than beginning index
        data.add_segment('SCI1', (0, 3), (0, 2))
    
    with pytest.raises(ValueError):
        # segment not on same order
        data.add_segment('SCI1', (0, 1), (1, 2))
    
    with pytest.raises(NameError):
        # duplicate label 
        data.add_segment('SCI1', (0, 1), (0, 2), label='test')
    
    with pytest.raises(ValueError):
        # Non-existent label
        data.remove_segment('SCI1', 'what')
        
if __name__ == "__main__":
    test()