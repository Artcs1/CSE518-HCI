# CSE518-HCI

## Install

1. Create a conda enviorenment

```
conda create --name py10-cse518 python=3.10
conda activate py10-cse518
```

2. Install the following package

```
pip install torch==2.5.1 torchvision==0.20.1 transformers==4.51.3 accelerate
python -m pip install paddlepaddle==3.0.0rc1 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
```

3. Install the requirements.txt

```
pip install -r requirements.txt
```

4. Download external models (PaddleOCR)
   
```
wget https://paddleocr.bj.bcebos.com/dygraph_v2.0/pgnet/e2e_server_pgnetA_infer.tar && tar xf e2e_server_pgnetA_infer.tar
```

5. Add a huggingface token
   
```
huggingface-cli login
```

6. Install ffmpeg
```
 sudo apt-get install ffmpeg
```
