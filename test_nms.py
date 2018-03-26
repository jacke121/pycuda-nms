# ----------------------------------------------------------------------------
# Copyright 2015-2016 Nervana Systems Inc.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ----------------------------------------------------------------------------
# pylint: skip-file

"""
Test of backend non-maximum supression compare with numpy results
The nms functions are tested on both GPU and CPU backends
"""
from __future__ import division
from __future__ import print_function

import itertools as itt

import numpy as np
from past.utils import old_div


def py_cpu_nms(dets, thresh):
    """Pure Python NMS baseline."""
    x1 = dets[:, 0]
    y1 = dets[:, 1]
    x2 = dets[:, 2]
    y2 = dets[:, 3]
    scores = dets[:, 4]

    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]

    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])

        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        inter = w * h
        ovr = old_div(inter, (areas[i] + areas[order[1:]] - inter))

        inds = np.where(ovr <= thresh)[0]

        order = order[inds + 1]

    return keep


def pytest_generate_tests(metafunc):

    thre_rng = [0.5, 0.7]
    count_rng = [300, 600, 1000]
    if 'fargs' in metafunc.fixturenames:
        fargs = itt.product(thre_rng, count_rng)
        metafunc.parametrize('fargs', fargs)


def test_nms(backend_pair, fargs):

    thre, box_count = fargs
    x1, y1, x2, y2, score = 0, 1, 2, 3, 4

    # dets = np.zeros((box_count, 5), dtype=np.float32)
    # dets[:, x1] = np.random.random((box_count,)) * 10
    # dets[:, x2] = dets[:, x1] + (np.random.random((box_count,)) * 10 + 400)
    # dets[:, y1] = np.random.random((box_count,)) * 10
    # dets[:, y2] = dets[:, y1] + (np.random.random((box_count,)) * 10 + 600)

    dets = np.asarray([[1, 2, 3, 4, 0.6], [1, 3, 3, 4, 0.7], [1, 1, 4, 4, 0.9], [2, 1, 4, 4, 0.85], [1, 1, 3, 4, 0.85]], dtype=np.float32)
    print(dets)
    dets[:, score] = np.sort(np.random.random((box_count,)))[::-1]

    ng, nc = backend_pair

    # call reference nms
    keep_ref = py_cpu_nms(dets, thre)

    # call cpu nms
    dets_nc = nc.array(dets)

    tic_cpu = nc.init_mark()
    toc_cpu = nc.init_mark()
    nc.record_mark(tic_cpu)

    keep_nc = nc.nms(dets_nc, thre)
    print("keep_nc nms", keep_nc)
    nc.record_mark(toc_cpu)
    nc.synchronize_mark(toc_cpu)
    print("cpu NMS time (ms): {}".format(nc.get_time(tic_cpu, toc_cpu)))

    assert keep_nc == keep_ref

    # call gpu nms kernel, the kernels takes sorted detection boxes
    dets_ng = ng.array(dets)
    scores = dets_ng[:, 4].get()
    order = scores.argsort()[::-1]

    sorted_dets_dev = dets_ng[order, :]

    tic_gpu = ng.init_mark()
    toc_gpu = ng.init_mark()

    # call through backend
    ng.record_mark(tic_gpu)

    keep_ng = ng.nms(sorted_dets_dev, thre)
    print("gpu nms",keep_ng)

    ng.record_mark(toc_gpu)
    ng.synchronize_mark(toc_gpu)
    print("gpu NMS time (ms): {}".format(ng.get_time(tic_gpu, toc_gpu)))

    assert keep_ng == keep_ref


if __name__ == '__main__':

    from neon.backends.nervanagpu import NervanaGPU
    from neon.backends.nervanacpu import NervanaCPU

    ng = NervanaGPU()
    nc = NervanaCPU()

    test_nms((ng, nc), (0.7, 5))
