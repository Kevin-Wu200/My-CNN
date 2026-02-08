"""
非监督分类测试脚本 - 使用真实遥感影像数据

测试目的：
1. 加载真实的TIFF遥感影像
2. 执行非监督分类
3. 识别并记录任何bug
4. 验证系统稳定性
"""

import sys
import os
import logging
from pathlib import Path
import traceback
import time

# 添加项目路径
sys.path.insert(0, '/Users/wuchenkai/深度学习模型')

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/wuchenkai/深度学习模型/test_unsupervised.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def test_unsupervised_classification():
    """测试非监督分类"""
    logger.info("=" * 80)
    logger.info("开始非监督分类测试")
    logger.info("=" * 80)
    
    try:
        # 导入必要的模块
        logger.info("导入模块...")
        from backend.utils.image_reader import ImageReader
        from backend.services.unsupervised_detection import UnsupervisedDiseaseDetectionService
        
        # 测试数据路径
        test_image_path = "/Users/wuchenkai/解译程序/20201023.tif"
        
        logger.info(f"测试数据路径：{test_image_path}")
        logger.info(f"文件大小：4.0GB")
        
        # 第一步：读取影像
        logger.info("\n第一步：读取影像文件...")
        start_time = time.time()
        
        image_reader = ImageReader()
        success, image_data, msg = image_reader.read_image(test_image_path)
        
        read_time = time.time() - start_time
        
        if not success:
            logger.error(f"❌ 影像读取失败：{msg}")
            return False
        
        logger.info(f"✅ 影像读取成功")
        logger.info(f"   影像尺寸：{image_data.shape}")
        logger.info(f"   数据类型：{image_data.dtype}")
        logger.info(f"   读取耗时：{read_time:.2f}秒")
        
        # 第二步：初始化检测服务
        logger.info("\n第二步：初始化非监督检测服务...")
        detection_service = UnsupervisedDiseaseDetectionService()
        logger.info("✅ 检测服务初始化成功")
        
        # 第三步：执行非监督分类
        logger.info("\n第三步：执行非监督分类...")
        logger.info("   参数：n_clusters=4, min_area=50")
        
        start_time = time.time()
        success, result, msg = detection_service.detect(
            image_data,
            n_clusters=4,
            min_area=50,
            task_manager=None,
            task_id=None
        )
        detect_time = time.time() - start_time
        
        if not success:
            logger.error(f"❌ 非监督分类失败：{msg}")
            return False
        
        logger.info(f"✅ 非监督分类成功")
        logger.info(f"   检测耗时：{detect_time:.2f}秒")
        logger.info(f"   检测结果：")
        logger.info(f"     - 聚类数：{result.get('n_clusters', 'N/A')}")
        logger.info(f"     - 候选区域数：{result.get('n_candidates', 'N/A')}")
        logger.info(f"     - 检测方法：{result.get('method', 'N/A')}")
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ 测试完成 - 所有步骤成功")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ 测试异常：{str(e)}")
        logger.error(f"异常类型：{type(e).__name__}")
        logger.error(f"异常堆栈：\n{traceback.format_exc()}")
        return False


def main():
    """主函数"""
    try:
        success = test_unsupervised_classification()
        return 0 if success else 1
    except Exception as e:
        logger.error(f"主函数异常：{str(e)}")
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
