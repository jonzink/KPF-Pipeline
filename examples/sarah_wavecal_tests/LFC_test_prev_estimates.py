from modules.wavelength_cal.src.wavelength_cal import WaveCalibrate

L1_file = config.ARGUMENT.input_dir + config.ARGUMENT.obs_prefix + config.ARGUMENT.obs_list[0] + '.fits'
rough_wls_file = config.ARGUMENT.master_wls_file + '.fits'
rough_wls = kpf1_from_fits(rough_wls_file, data_type='NEID')['CALWAVE']

lfc_l1_obj = kpf1_from_fits(L1_file, data_type='NEID')
f0 = config.ARGUMENT.f0_key
fr = config.ARGUMENT.frep_key
output_ext = config.ARGUMENT.output_ext
orderlette_names = config.ARGUMENT.cal_orderlette_name
quicklook = config.ARGUMENT.quicklook

# use wls from L1 NEID file as master solution
wave_soln = WaveCalibrate(
    lfc_l1_obj, 'LFC', orderlette_names, True, quicklook, 'NEID', output_ext,
    rough_wls = rough_wls, f0_key=f0, frep_key=fr, prev_wl_pixel_ref=
)

# TODO: save output to correct location, use prev mode estimates

obsname = config.ARGUMENT.obs_prefix + config.ARGUMENT.obs_list[0]
output_filename = config.ARGUMENT.output_dir + obsname + config.ARGUMENT.lev1_suffix + '_wave' + '.fits'
result = to_fits(wave_soln, output_filename)