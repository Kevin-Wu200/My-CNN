<template>
  <div class="model-config-page">
    <Card class="config-card">
      <div class="card-header">
        <h2>模型构建与参数配置</h2>
      </div>

      <div class="config-section">
        <label class="config-item">
          <span class="label-text">CNN 主干类型</span>
          <select v-model="config.cnnBackbone" class="select-input">
            <option value="">请选择</option>
            <option value="resnet50">ResNet50</option>
            <option value="resnet101">ResNet101</option>
            <option value="vgg16">VGG16</option>
            <option value="efficientnet">EfficientNet</option>
          </select>
        </label>

        <label class="config-item">
          <span class="label-text">时序建模模块类型</span>
          <select v-model="config.temporalModule" class="select-input">
            <option value="">请选择</option>
            <option value="lstm">LSTM</option>
            <option value="gru">GRU</option>
            <option value="transformer">Transformer</option>
            <option value="3dcnn">3D CNN</option>
          </select>
        </label>

        <label class="config-item">
          <span class="label-text">输入样本类型</span>
          <select v-model="config.inputType" class="select-input">
            <option value="">请选择</option>
            <option value="pixel">像素级</option>
            <option value="superpixel">超像素级</option>
          </select>
        </label>
      </div>

      <div class="advanced-section">
        <ToggleButton :isOpen="showAdvanced" @toggle="showAdvanced = !showAdvanced">
          高级参数
        </ToggleButton>

        <div v-if="showAdvanced" class="advanced-params">
          <label class="config-item">
            <span class="label-text">学习率</span>
            <input
              v-model.number="config.learningRate"
              type="number"
              step="0.0001"
              class="input-field"
              placeholder="0.001"
            />
          </label>

          <label class="config-item">
            <span class="label-text">批大小</span>
            <input
              v-model.number="config.batchSize"
              type="number"
              class="input-field"
              placeholder="32"
            />
          </label>

          <label class="config-item">
            <span class="label-text">训练轮数</span>
            <input
              v-model.number="config.epochs"
              type="number"
              class="input-field"
              placeholder="100"
            />
          </label>
        </div>
      </div>

      <div class="action-buttons">
        <Button variant="secondary" @click="goToPreviousStep">
          上一步
        </Button>
        <Button variant="primary" @click="goToNextStep">
          下一步
        </Button>
      </div>
    </Card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import Card from '@/components/common/Card.vue'
import Button from '@/components/common/Button.vue'
import ToggleButton from '@/components/common/ToggleButton.vue'

const router = useRouter()
const showAdvanced = ref(false)

const config = ref({
  cnnBackbone: '',
  temporalModule: '',
  inputType: '',
  learningRate: 0.001,
  batchSize: 32,
  epochs: 100,
})

const goToPreviousStep = () => {
  router.push('/training/preprocess')
}

const goToNextStep = () => {
  router.push('/training/training')
}
</script>

<style scoped>
.model-config-page {
  display: flex;
  justify-content: center;
  padding: 24px;
}

.config-card {
  width: 100%;
  max-width: 600px;
}

.card-header {
  margin-bottom: 24px;
}

.card-header h2 {
  font-size: 20px;
  font-weight: 600;
  color: #333;
  margin: 0;
}

.config-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 24px;
}

.config-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.label-text {
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.select-input,
.input-field {
  padding: 10px 12px;
  border: 1px solid #d0d0d0;
  border-radius: 8px;
  font-size: 14px;
  transition: all 0.2s;
}

.select-input:focus,
.input-field:focus {
  outline: none;
  border-color: #0066cc;
  box-shadow: 0 0 0 3px rgba(0, 102, 204, 0.1);
}

.advanced-section {
  margin-bottom: 24px;
}

.advanced-params {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 16px;
  padding: 16px;
  background-color: #f9f9f9;
  border-radius: 8px;
}

.action-buttons {
  display: flex;
  gap: 12px;
  margin-top: 24px;
}

.action-buttons button {
  flex: 1;
}
</style>
