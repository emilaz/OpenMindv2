import sys

sys.path.append('..')

import vis.classification_vis as cvis
import vis.brain_vis as bvis
from data_creation.data_provider import *
import util.classification_utils as util
import util.data_utils as dutil

import numpy as np

from sklearn.model_selection import StratifiedKFold
from sklearn.ensemble import RandomForestClassifier
import os
import glob

from itertools import product
from multiprocessing import Pool


def train_and_save_best_classifier(results, x, y, configs):
    best_n, best_d, best_f = util.get_best_hyperparas(results, 'AVG PR')
    classifier = RandomForestClassifier(n_estimators=int(best_n), max_depth=int(best_d), max_features=int(best_f),
                                        random_state=0)  # init classifier
    classifier.fit(x, y)
    best_thr = util.get_optimal_threshold(classifier, x, y,
                                          go_after_pr=True)  # get threshold using cv (on whole dataset)
    dutil.save_classifier(classifier, best_thr, configs, 'RF')


# Run classifier with cross-validation
def calc_results_and_save(x, y, configs):
    cv = StratifiedKFold(n_splits=10, shuffle=False, random_state=1)
    # dataframe for saving results
    results = pd.DataFrame(columns=('Number Estimators', 'Max Depth', 'Max Features', 'AVG PR'))  # ,'AUC ROC'))
    # do random search on parameters
    no_params = 30
    est = np.random.choice(np.arange(130)[5:], no_params)
    max_d = np.random.choice(np.arange(60)[1:], no_params)
    max_f = np.random.choice(np.arange(min(x.shape))[1:], no_params)

    # Search for best hyperpara combo with cross validation
    for idx, (c, d, f) in enumerate(zip(est, max_d, max_f)):
        classifier = RandomForestClassifier(n_estimators=c, max_depth=d, max_features=f,
                                            random_state=0)  # init classifier
        auc_pr = util.get_auc_score(classifier, cv, x, y, go_after_pr=True)
        # auc_roc =util.get_auc_score(classifier, cv, x, y, go_after_pr=False)
        results.loc[idx] = [c, d, f, auc_pr]
        print('Number Estimators= %d, Max Depth = %d, Max Feat = %d, AUC PR %.3f' % (c, d, f, auc_pr))
    dutil.save_results(results, configs, 'RF')  # save results for later use
    return results


def vis_results(x, y, x_ev, y_ev, configs):
    # using hyperpara found, evaluate and get pretty plots
    # get f1 scores on whole training set
    classifier, best_thr = dutil.load_classifier(configs, 'RF')
    y_pred = util.get_prediction(classifier, x, best_thr)
    y_pred_ev = util.get_prediction(classifier, x_ev, best_thr)

    # draw pretty plots
    title = dutil.generate_graph_link(configs)
    cvis.score_heatmap(y_pred, y, title + ' Metrics Train Set', 'Metrics Train Set')
    cvis.score_heatmap(y_pred_ev, y_ev, title + ' Metrics Test Set', 'Metrics Test Set')
    cvis.conf_mat(y_pred, y, title + ' Confusion Matrix Train Set', 'Confusion Matrix Train Set')
    cvis.conf_mat(y_pred_ev, y_ev, title + ' Confusion Matrix Test Set', 'Confusion Matrix Test Set')

    cvis.plot_roc(x, y, classifier, title + ' ROC Train Set', 'ROC Train Set')
    cvis.plot_roc(x_ev, y_ev, classifier, title + ' ROC Test Set', 'ROC Test Set')
    cvis.plot_pr_curve(x, y, classifier, title + ' Precision Recall Curve Train Set', 'Precision Recall Curve Train Set')
    cvis.plot_pr_curve(x_ev, y_ev, classifier, title + ' Precision Recall Curve Test Set', 'Precision Recall Curve Test Set')

    # draw brain map and the most important hyperparameter
    # get brain map
    h5_fn = dutil.get_h5fn_file(configs['patient'][0])
    # print('WARNING. NO BRAIN IS CURRENTLY BEING PLOTTED. YOU SURE YOU WANT THIS?')
    bvis.plot_all(h5_fn, configs)

def do_all(file, cut, reload=False):
    provider = DataProvider()
    configs = dutil.generate_configs_from_file(file, cut)
    print(configs)
    x, y, x_ev, y_ev = provider.get_data(configs, reload=True)
    print(x.shape, y.shape, x_ev.shape, y_ev.shape)
    print("Happy: Train {} Test {}, Not Happy: Train {} Test {}".format(sum(y==1), sum(y_ev==1),sum(y==0), sum(y_ev==0)))
    if reload:
        try:
            dutil.load_results(configs, 'RF')
        # this assumes we just want to visualize
        except FileNotFoundError as e:
            print(configs)
            print(e)
            reload = False
    if not reload:
        res = calc_results_and_save(x, y, configs)
        # best classifier is the one with best AUC (PR or ROC)
        train_and_save_best_classifier(res, x, y, configs)

    vis_results(x, y, x_ev, y_ev, configs)
    print('Done.', configs)


def randomize_labels(y):
    ones = int(np.sum(y))
    # where?
    fill_ones = np.random.choice(len(y), ones, replace=False)
    ret = np.empty(len(y))
    ret[:] = 0
    ret[fill_ones] = 1
    return ret


if __name__ == '__main__':
    files = [f for f in os.listdir("/home/emil/EmoCog/data/new_labels/train_test_datasets/['cb46fd46']") if '100' in f and '5' in f ]
    #          if "['cb46" in f and "[[3, 4]]" not in f and '[[7]]' not in f]
    # lell = [itertools.combinations([3,4,5,6,7,8], c) for c in [5,6]]
    # day_combos = [str(list(v)) for s in lell for v in s]
    # files = [f for f in os.listdir("/home/emil/EmoCog/data/new_labels/train_test_datasets/['cb46fd46']")
    #          # for dayz in day_combos
    #          if '100' in f
    #          # and dayz in f
    #          and 'shuffle_True' in f
    #          and 'sliding_False' in f]
    # files = [os.path.basename(f) for f in glob.glob('/home/emil/EmoCog/data/new_labels/train_test_datasets/**/*')]

    cuts = [.2]
    reload = [False]
    all_elements = [files, cuts, reload]

    file_cut_combos = []
    for allel in product(*all_elements):
        file_cut_combos += [allel]

    pool = Pool(8)
    yass = pool.starmap(do_all, file_cut_combos)

    del pool
    del yass
