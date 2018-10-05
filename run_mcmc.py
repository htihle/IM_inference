# To run: screen -dm bash -c 'script -c "mpiexec -n 48 python run_mcmc.py" output.txt' 

"""
Script to do MCMC inference from data.

The experiment setup is configured in the
"experiment_params.py" file, while the setup
for the mcmc-run is configured in the
"mcmc_params.py" file.

Basically, we take some input data (corresponding
to a set of observables) and constrain the model
parameters of some IM-model.
"""
import numpy as np
import src.MapObj
import src.tools
import src.Model
import src.Observable
import src.likelihoods
import emcee

# from schwimmbad import MPIPool # In future emcee release
from emcee.utils import MPIPool
import sys
import os
import datetime
import importlib

os.environ["OMP_NUM_THREADS"] = "1"

if len(sys.argv) < 2:
    import mcmc_params
    import experiment_params as exp_params
else:
    mcmc_params = importlib.import_module(sys.argv[1][:-3])
    exp_params = importlib.import_module(sys.argv[2][:-3])


def lnprob(model_params, model, observables, map_obj):
    """
    Simulates the experiment for given model parameters to estimate the
    mean of the observables and uses this mean to estimate the
    likelihood.
    """
    # Simulate the required number of realizations in order
    # to estimate the mean value of the different observables
    # at the current model parameters.
    ln_prior = 0.0
    ln_prior += model.ln_prior(model_params,
                               mcmc_params.prior_params[model.label])
    if not np.isfinite(ln_prior):
        return -np.infty
    for i in range(mcmc_params.n_realizations):
        map_obj.map = src.tools.gaussian_smooth(
            model.generate_map(model_params), map_obj.sigma_x,
            map_obj.sigma_y) + map_obj.generate_noise_map()
        map_obj.map -= np.mean(map_obj.map.flatten())
        map_obj.calculate_observables(observables)
        for observable in observables:
            observable.add_observable_to_sum()
    for observable in observables:
        observable.calculate_mean(mcmc_params.n_realizations)

    # calculate the actual likelihoods
    ln_likelihood = 0.0
    if (mcmc_params.likelihood == 'chi_squared'):
        for observable in observables:
            ln_likelihood += \
                src.likelihoods.ln_chi_squared(
                    observable.data,
                    observable.mean,
                    observable.independent_var / mcmc_params.n_patches
                )
    elif (mcmc_params.likelihood == 'chi_squared_cov'):
        n_data = len(mcmc_params.cov_mat_0[:, 0])
        i = 0
        data = np.zeros(n_data)
        mean = np.zeros(n_data)
        ind_var = np.zeros(n_data)
        for observable in observables:
            n_data_obs = len(observable.data)
            data[i:i + n_data_obs] = observable.data
            mean[i:i + n_data_obs] = observable.mean
            ind_var[i:i + n_data_obs] = observable.independent_var
            i += n_data_obs
        var_ratio = np.sqrt(
            np.outer(ind_var, ind_var)
            / np.outer(mcmc_params.ind_var_0, mcmc_params.ind_var_0)
        )
        cov_mat = mcmc_params.cov_mat_0 * var_ratio / mcmc_params.n_patches
        ln_likelihood += src.likelihoods.ln_chi_squared_cov(
            data, mean, cov_mat)

    if not np.isfinite(ln_likelihood):
        return -np.infty

    return ln_prior + ln_likelihood


if __name__ == "__main__":
    if mcmc_params.pool: 
        pool = MPIPool(loadbalance=True)
        if not pool.is_master():
            pool.wait()
            sys.exit(0)

    start_time = datetime.datetime.now()
    mcmc_chains_fp, mcmc_log_fp, samples_log_fp, runid = \
        src.tools.make_log_file_handles(mcmc_params.output_dir)
    src.tools.make_picklable(exp_params, mcmc_params)

    model, observables, map_obj = src.tools.set_up_mcmc(
        mcmc_params, exp_params)

    src.tools.get_data(mcmc_params, exp_params, model, observables, map_obj)

    if mcmc_params.pool:
        sampler = emcee.EnsembleSampler(
            mcmc_params.n_walkers, model.n_params, lnprob,
            args=(model, observables, map_obj), pool=pool)
    else:
        sampler = emcee.EnsembleSampler(
            mcmc_params.n_walkers, model.n_params, lnprob,
            args=(model, observables, map_obj), threads=mcmc_params.n_threads)
    pos = model.mcmc_walker_initial_positions(
        mcmc_params.prior_params[model.label], mcmc_params.n_walkers)
    samples = np.zeros((mcmc_params.n_steps,
                        mcmc_params.n_walkers,
                        model.n_params))

    i = 0
    
    while i < mcmc_params.n_steps:
        print('starting iteration %i out of %i of run %i' % (
            i + 1, mcmc_params.n_steps, runid),
            datetime.datetime.now() - start_time)
        sys.stdout.flush()
        for result in sampler.sample(pos, iterations=1, storechain=True):
            samples[i], _, blobs = result
            pos = samples[i]
            with open(mcmc_chains_fp, 'a') as chains_file:
                for j in range(mcmc_params.n_walkers):
                    chains_file.write('{0:4d} {1:s}\n'.format(                                                     
                        j, ' '.join([str(p) for p in pos[j]])))
            sys.stdout.flush()
            i += 1
    if mcmc_params.pool:
        pool.close()
                         
    np.save(mcmc_params.samples_filename, samples)

    src.tools.write_log_file(mcmc_log_fp, samples_log_fp, start_time, samples)
