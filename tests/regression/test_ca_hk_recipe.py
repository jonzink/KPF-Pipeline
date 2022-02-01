# test_ca_hk_recipe.py
from kpfpipe.tools.recipe_test_unit import recipe_test

ca_hk_recipe = """# test recipe for Ca HK extraction on KPF simulated data
from modules.ca_hk.src.ca_hk_extraction import CaHKExtraction
test_data_dir = KPFPIPE_TEST_DATA + '/KPF_Simulated_Data/HK/' 
data_type = config.ARGUMENT.data_type
output_dir = config.ARGUMENT.output_dir

input_hk_pattern = test_data_dir + config.ARGUMENT.input_lev0_hk_pattern
input_trace_file = test_data_dir + config.ARGUMENT.input_trace_path

fiber_list = config.ARGUMENT.fiber_list
lev1_stem_suffix = config.ARGUMENT.output_lev1_suffix
output_exts = config.ARGUMENT.output_exts

for hk_file in find_files(input_hk_pattern):
    _, short_hk_flat = split(hk_file)
    lev0_flat_stem, lev0_flat_ext = splitext(short_hk_flat)
    hk_data = kpf0_from_fits(hk_file, data_type="NEID")
    output_hk_file = output_dir + lev0_flat_stem + '_hk' + lev1_stem_suffix + '.fits'
    output_data = None
    output_lev1_hk = CaHKExtraction(hk_file, input_trace_file, fiber_list, output_data, output_exts=output_exts)
"""

ca_hk_config = "examples/default_hk.cfg"

def test_recipe_ca_hk_kpf():
    recipe_test(ca_hk_recipe, ca_hk_config)
