import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.nn.init as init

def _weights_init(m):
    classname = m.__class__.__name__
    if isinstance(m, nn.Linear) or isinstance(m, nn.Conv2d):
        init.kaiming_normal_(m.weight)

class Linear(nn.Module):
    def __init__(self, in_dim, out_dim, requires_grad):
        super(Linear, self).__init__()  
        self.w = nn.Parameter(torch.randn(in_dim, out_dim), requires_grad=requires_grad)
        self.b = nn.Parameter(torch.randn(out_dim), requires_grad=requires_grad)

    def forward(self, x):
        x = x.matmul(self.w) 
        y = x + self.b.expand_as(x)
        return y

class BasicBlock(nn.Module):

    def __init__(self, in_planes, planes, stride=1,scaler=1.,expansion=1):
        super(BasicBlock, self).__init__()

        self.shortcut = True if stride==1 else False
        self.scaler = scaler

        self.conv1 = nn.Conv2d(in_planes, expansion*planes, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(expansion*planes)

        self.conv2 = nn.Conv2d(expansion*planes, planes, kernel_size=1, stride=1, padding=0, bias=False)
        self.bn2 = nn.BatchNorm2d(planes)


        self.conv3 = nn.Conv2d(planes, planes, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn3 = nn.BatchNorm2d(planes)
        self.shortcut = nn.Sequential()
        if stride != 1 or in_planes != planes:
           self.shortcut = nn.Sequential(
                                        nn.Conv2d(in_planes, planes, kernel_size=1, stride=stride, bias=False),
                                        nn.BatchNorm2d(planes)
                                        )

    def forward(self, x):
        #print(self.scaler)
        out = self.bn1(self.conv1(x))
        # self.scaler is set to 1 for large model training, then set to 0 for depth pruning and finetuning. 
        out = self.scaler*F.relu(out) + (1-self.scaler)*out

        out = self.bn2(self.conv2(out))
        out = F.relu(out)

        out = self.bn3(self.conv3(out))
        out = out + self.shortcut(x) 
        return out

 
class ReduceNet(nn.Module):
    def __init__(self, block, num_blocks, num_classes=10, width_scaler=1, expansion=1):
        super(ReduceNet, self).__init__()

        self.requires_grad =nn.Parameter(torch.tensor(True), requires_grad=False)
        self.scaler = nn.Parameter(torch.tensor(1.), requires_grad=False)

        self.in_planes = 16*width_scaler

        self.conv1 = nn.Conv2d(3, 16*width_scaler, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(16*width_scaler)

        self.layer1 = self._make_layer(block, 16*width_scaler, num_blocks[0], stride=1, scaler=self.scaler, expansion=expansion)
        self.layer2 = self._make_layer(block, 32*width_scaler, num_blocks[1], stride=2, scaler=self.scaler, expansion=expansion)
        self.layer3 = self._make_layer(block, 64*width_scaler, num_blocks[2], stride=2, scaler=self.scaler, expansion=expansion)
        self.linear = Linear(64*width_scaler, num_classes, self.requires_grad.item())

        self.apply(_weights_init)

    def _make_layer(self, block, planes, num_blocks, stride, scaler,expansion):

        strides = [stride] + [1]*(num_blocks-1)
        layers = []
        for stride in strides:
            layers.append(block(self.in_planes, planes, stride, scaler, expansion))
            self.in_planes = planes 

        return nn.Sequential(*layers)

    def forward(self, x):
        
        out = self.bn1(self.conv1(x))
        out = F.relu(out,inplace=True)

        out = self.layer1(out)
        out = self.layer2(out)
        out = self.layer3(out)

        out = F.avg_pool2d(out, out.size()[3])
        out = out.view(out.size(0), -1)
        out = self.linear(out)

        return out


def reducenet20(num_classes,expansion):
    return ReduceNet(BasicBlock, [3, 3, 3],num_classes, expansion=expansion)


def reducenet56(num_classes,expansion):
    return ReduceNet(BasicBlock, [9, 9, 9],num_classes, expansion=expasion)
