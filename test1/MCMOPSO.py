import math
import random
import time
from collections import Counter

import numpy
import numpy as np
from sklearn.cross_decomposition import PLSRegression
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import KFold
from mrmr import mrmr_regression
import pandas as pd
def get_10fold_cv_pls(X, y):
    """
    十折交叉验证，返回y_predicts, loo_RMSE, loo_R2
    :param pls: 模型
    :param X: 特征集合, 要求是矩阵类型或者ndarray
    :param y: 因变量
    :return: y_predicts, loo_RMSE, loo_R2
    """
    row, column = X.shape
    y_predicts = np.zeros((row, 1))  # 存放测试集的预测结果
    pls = PLSRegression(n_components=3)  # 实例化pls模型，成分为1
    kf = KFold(n_splits=10)  # 十折交叉验证
    for train_index, test_index in kf.split(X):
        x_train, y_train = X[train_index], y[train_index]
        x_test, y_test = X[test_index], y[test_index]
        pls.fit(x_train, y_train)  # 训练集建模
        y_predicts[test_index] = pls.predict(x_test)  # 预测
    return y_predicts

# select top 10 features using mRMR



def updatePBest(pBest, pFits: object, pops, fits):
    nPop, nF = fits.shape
    isDom1 = fits < pFits
    isDom2 = fits <= pFits
    isCh = (np.sum(isDom1, axis=1) == nF) & (np.sum(isDom2, axis=1) >= 1)
    if np.sum(isCh) >= 1:
        # 种群中的解支配pBest的话更新pBest
        pBest[isCh] = pops[isCh]
        pFits[isCh] = fits[isCh]
    return pBest, pFits


def getNonDominationPops(pops, fits):
    """快速得到非支配解集
    Params:
        pops: 种群，nPop * nChr 数组
        fits: 适应度， nPop * nF 数组
    Return:
        ranks: 每个个体所对应的等级，一维数组
    """
    nPop = pops.shape[0]
    nF = fits.shape[1]  # 目标函数的个数:2
    ranks = np.ones(nPop, dtype=np.int32)#创建nPop个数组，元素值设为1
    nPs = np.zeros(nPop)  # 每个个体p被支配解的个数
    for i in range(nPop):
        for j in range(nPop):
            if i == j:
                continue
            isDom1 = fits[i] <= fits[j]
            isDom2 = fits[i] < fits[j]
            # 是否被支配-> i被j支配
            if sum(~isDom2) == nF and sum(~isDom1) >= 1:
                nPs[i] += 1
    r = 0  # 当前等级为 0， 等级越低越好
    indices = np.arange(nPop)
    rIdices = indices[nPs == 0]  # 当前被支配数为0的索引
    ranks[rIdices] = 0

    return pops[ranks == 0], fits[ranks == 0]


def updateArchive(pops, fits, archive, arFits):
    """根据当前新的种群更新archive
    Return:
        newArchive
        newArFit
    """
    # 获取当前种群的非支配解
    nonDomPops, nonDomFits = getNonDominationPops(pops, fits)
    isCh = np.zeros(nonDomPops.shape[0]) >= 1  # 开始全部设置为false
    nF = fits.shape[1]  # 目标个数
    for i in range(nonDomPops.shape[0]):
        # 判断arFits中是否有解支配当前种群的非支配解
        isDom1 = nonDomFits[i] >= arFits
        isDom2 = nonDomFits[i] > arFits
        isDom = (np.sum(isDom1, axis=1) == nF) & \
            (np.sum(isDom2, axis=1) >= 1)
        if np.sum(~isDom) >= 1:
            # 说明archive集中没有一个解可以支配该解，那么将其添加进去
            isCh[i] = True  # 设置为可供选择
    # 如果有支配解产生
    if np.sum(isCh) >= 1:
        archive = np.concatenate((archive, nonDomPops[isCh]), axis=0)
        arFits = np.concatenate((arFits, nonDomFits[isCh]), axis=0)
    return archive, arFits


def initPops(nPop, nChr,lb,rb,Vmax, Vmin):
    pops = np.zeros((nPop, nChr))
    for i in range(nPop):
        for j in range(nChr):
            pops[i, j] = random.randint(0, 1)
    # VPops = np.random.rand(nPop, nChr)*(Vmax-Vmin) + Vmin
    VPops = np.zeros((nPop, nChr))
    for i in range(nPop):
        for j in range(nChr):
            VPops[i, j] = random.randint(0, 1) * (Vmax - Vmin) + Vmin
    return pops, VPops



def getPosition(archive, arFits, M):
    """获得当前archive集的位置
    Params：
        archive: archive集
        arFits：对应的适应度
        M: 划分的网格大小为M*M
    Return：
        flags: 每个粒子对应的位置, nF维映射为1位
    """
    fmin = np.min(arFits, axis=0)
    fmax = np.max(arFits, axis=0)
    grid = (fmax-fmin)/M  # 网格的长宽
    pos = np.ceil((arFits-fmin)/grid)
    nA, nF = pos.shape
    flags = np.zeros(nA)
    for dim in range(nF-1):
        flags += (pos[:, dim] - 1) * (M**(nF-dim-1))
    flags += pos[:,-1]
    return flags




def getGBest(pops, fits, archive, arFits, M):
    # 根据密度来从archive集中选择gBest
    nPop, nChr = pops.shape
    nF = fits.shape[1]
    gBest = np.zeros((nPop, nChr))
    flags = getPosition(archive, arFits, M)
    # 统计每个网格出现的次数
    counts = Counter(flags).most_common()
    for i in range(nPop):
        # 首先从archive中寻找没有被pops[i]支配的集合
        isDom1 = fits[i] <= arFits
        isDom2 = fits[i] < arFits
        isDom = (np.sum(isDom1, axis=1) == nF) & (np.sum(isDom2, axis=1)>=1)
        # 之前的isDom是指pop[i]能够支配archive的集合，这里要取反
        isDom = ~isDom
        if np.sum(isDom) == 0:
            gBest[i] = pops[i]
            continue
        elif np.sum(isDom) == 1:
            gBest[i] = archive[isDom]
            continue
        archivePop = archive[isDom]
        # archivePopFit = arFits[isDom]
        # 找出ai集中每个个体所处的位置
        aDomFlags = flags[isDom]
        # 统计每个网格出现的次数
        counts = Counter(aDomFlags).most_common()
        minFlag, minCount = counts[-1]  # 出现次数最少的网格及其次数
        # 可能有多个网格的出现的次数相同，并且同样次数最小
        minFlags = [counts[i][0] for i in range(len(counts))
                    if counts[i][1]==minCount]
        isCh = False
        for minFlag in minFlags:
            isCh = isCh | (aDomFlags == minFlag)
        indices = np.arange(aDomFlags.shape[0])# 索引
        chIndices = indices[isCh]#等于0或1

        # 从待选集中随机选择一个
        idx = chIndices[int(np.random.rand()*len(chIndices))]
        if np.sum(idx)==0:
            idx = chIndices[int(np.random.rand() * len(chIndices))]
        gBest[i] = archivePop[idx]  # 复制给相应的gBest位置上
    return gBest





def function(X):
    index = np.where(X == 1)[0]
    sample_data = data.values[:, index]  # 列索引
    # print(sample_data.shape[1])
    # if (sample_data.shape[1] == 0 ):
    #     return np.inf, np.inf

    num = np.sum(X == 1)
    # f1 = num/len(X)
    if num == 0 or num == 1 or num == 2:
        return np.inf, np.inf

    pr = get_10fold_cv_pls(sample_data, data_label)
    RMSE = np.sqrt(mean_squared_error(data_label, pr))
    return num, RMSE


def fitness(pops,func):
    nPop = pops.shape[0]
    fits = np.array([func(pops[i]) for i in range(nPop)])
    return fits


def checkArchive(archive, arFits, nAr, M):
    """
    检查archive集是否超出了规模。
    如果超出了规模那么采取减少操作
    """
    if archive.shape[0] <= nAr:
        return archive, arFits
    else:
        nA = archive.shape[0]  # 当前解集大小
        flags = getPosition(archive, arFits, M)
        # 统计每个网格出现的次数
        counts = Counter(flags).most_common()
        # 选择原始archive集
        isCh = np.array([True for i in range(nA)])
        indices = np.arange(nA)  # 原始索引
        for i in range(len(counts)):
            if counts[i][-1] > 1:
                # 删除当前网格counts[i][0]的粒子数
                pn = int((nA-nAr)/nA*counts[i][-1]+0.5)
                # if counts[i][-1] >= 10:
                #     pn = counts[i][-1] // 2
                # 当前要删除的网格中的所有粒子的索引
                gridIdx = indices[flags==counts[i][0]].tolist()
                pIdx = random.sample(gridIdx, pn)
                isCh[pIdx] = False  # 删除这些元素
        archive = archive[isCh]
        arFits = arFits[isCh]
        return archive, arFits


def MOPSO(nIter, nPop, nAr, nChr, func, c1f,c2f,c1i,c2i, lb, rb, Vmax, Vmin, M):
    """多目标粒子群算法
    Params:
        nIter: 迭代次数
        nPOp: 粒子群规模
        nAr: archive集合的最大规模
        nChr: 粒子大小
        func: 优化的函数
        c1、c2: 速度更新参数
        lb: 解下界
        rb：解上界
        Vmax: 速度最大值
        Vmin：速度最小值
        M: 划分的栅格的个数为M*M个
    Return:
        paretoPops: 帕累托解集
        paretoPops：对应的适应度
    """
    # 种群初始化
    pops, VPops = initPops(nPop, nChr, lb, rb, Vmax, Vmin)
    # 获取个体极值和种群极值
    fits = fitness(pops, func)
    pBest = pops
    pFits = fits
    gBest = pops
    # 初始化archive集, 选取pops的帕累托面即可
    archive, arFits = getNonDominationPops(pops, fits)
    wStart = 0.95
    wEnd = 0.4

    # 开始主循环
    iter = 1
    while iter <= nIter:
        print("【进度】【{0:20s}】【正在进行{1}代...】【共{2}代】".\
            format('▋'*int(iter/nIter*20), iter, nIter), end='\r')

        # 速度更新
        c1 = c1f + (c1i-c1f) * (iter / nIter)
        c2 = c2f + (c2f - c2i) * iter / nIter
        # w = (wStart-wEnd) * (iter/nIter)**2+(wEnd-wStart)*(2*iter/nIter)+wStart
        w = (wStart-wEnd)*(iter/nIter-1)**2+wEnd

        VPops = w*VPops + c1*np.random.rand()*(pBest-pops) + c2*np.random.rand()*(gBest-pops)
        VPops[VPops>Vmax] = Vmax
        VPops[VPops<Vmin] = Vmin
        # 坐标更新
        pops += VPops
        pops[pops<lb] = lb
        pops[pops>rb] = rb  # 防止过界
        fits = fitness(pops, func)


        # 更新个体极值
        pBest, pFits = updatePBest(pBest, pFits, pops, fits)
        # 更新archive集
        archive, arFits = updateArchive(pops, fits, archive, arFits)
        # 检查是否超出规模，如果是，那么剔除掉一些个体
        archive, arFits = checkArchive(archive, arFits, nAr, M)
        gBest = getGBest(pops, fits, archive, arFits, M)  # 重新获取全局最优解
        # pos = 0.9 - ((iter+1) / nIter) * (0.9 - 0.4)
        # # print(pos)
        # cauchy = numpy.random.standard_cauchy(1)
        # # print(cauchy)
        # gBest = gBest * (1 + cauchy)

        iter += 1
    print('\n')
    paretoPops, paretoFits = getNonDominationPops(archive, arFits)
    return paretoPops, paretoFits


def napp():
    nIter = 300
    nPop = 100
    nChr = 79
    nAr = 50
    func = function
    c1f = 2.75
    c1i = 1.25
    c2i = 0.5
    c2f = 2.25
    lb = 0
    rb = 1
    Vmax = 0.6
    Vmin = -0.6
    M = 20
    paretoPops, paretoFits = MOPSO(nIter, nPop, nAr, nChr, func, c1f,c2f,c1i,c2i, lb, rb, Vmax, Vmin, M)
    return paretoPops, paretoFits

def get_index(paretoPops, c):
    ans = []
    for item in paretoPops:
        tmp = []
        for k in range(len(item)):
            if item[k] == 1:
                tmp.append(c[k])
        ans.append(tmp)
    return ans


if __name__ == "__main__":
    df_x = pd.read_excel(r'C:\Users\Administrator\Desktop\data1\ExogenousSubstance.xlsx', sheet_name='Sheet1',index_col=0)  # 内源性物质
    df_y = pd.read_excel(r'C:\Users\Administrator\Desktop\data1\DrugEffectIndex(1).xlsx', sheet_name='Sheet1',index_col=0)
    # df_x = pd.read_excel(r'C:\Users\Administrator\Desktop\paper2回归任务\data\blogData_test\blogData_test6.xlsx')  # 内源性物质
    # df_x = pd.read_excel( r'C:\Users\Administrator\Desktop\paper2回归任务\data\data big sample\ResidentialBuildingDataSet.xlsx',index_col=0)  # 内源性物质
    # df_y = pd.read_excel(r'C:\Users\Administrator\Desktop\paper2回归任务\data\data big sample\ResidentialBuildingDataSety.xlsx', index_col=0)
    # df_y = pd.read_excel(r'C:\Users\Administrator\Desktop\paper2回归任务\data\data big sample\ResidentialBuildingDataSety.xlsx',index_col=0)
    X = df_x
    # # print(X)
    y = df_y['y1']
    # X = df_x.iloc[:,:-3]
    # # print(X)
    # y = df_x['y1']
    # print(y)0.
    #1.mrmr

    selected_features = ['x634', 'x700', 'x456', 'x324', 'x454', 'x457', 'x587', 'x541', 'x373', 'x374', 'x547', 'x391', 'x530', 'x468', 'x451', 'x469', 'x455', 'x447', 'x554', 'x445', 'x565', 'x446', 'x392', 'x383', 'x523', 'x555', 'x419', 'x594', 'x350', 'x566', 'x382', 'x515', 'x540', 'x595', 'x398', 'x400', 'x390', 'x337', 'x341', 'x470', 'x607', 'x516', 'x365', 'x462', 'x364', 'x360', 'x384', 'x458', 'x279', 'x572', 'x590', 'x375', 'x550', 'x395', 'x773', 'x518', 'x349', 'x615', 'x557', 'x536', 'x511', 'x363', 'x538', 'x524', 'x376', 'x461', 'x558', 'x624', 'x466', 'x336', 'x625', 'x367', 'x778', 'x368', 'x369', 'x434', 'x342', 'x583', 'x649']
    action = time.time()
    print(action)

    #2.mopso
    data = X[selected_features]
    # data = X
    Xname = X.columns.tolist()
    # print(data)
    data_label = y.values
    paretoPops, paretoFits = napp()
    print(np.unique(paretoFits,axis=0))
    # print(paretoPops)
    FS = get_index(paretoPops, Xname)
    # R2 = r2_score(y, get_10fold_cv_pls(X[FS[1]].values, y))
    # print('两阶段的R：', R2)
    FS = list(set([tuple(t) for t in FS]))
    FS = [list(s) for s in FS]
    FS = sorted(FS,key=lambda x:len(x))
    print(FS)
    end = time.time()
    print('时间', end - action)
