-- 名言采集结果表：正文 MD5 指纹做唯一索引，配合 ON DUPLICATE KEY UPDATE 防重入库
USE crawler_lab;

CREATE TABLE IF NOT EXISTS quotes (
  id         INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  text_hash  CHAR(32)      NOT NULL COMMENT '正文 MD5 指纹（防重业务主键）',
  text       TEXT          NOT NULL COMMENT '名言正文',
  author     VARCHAR(100)  NOT NULL COMMENT '作者',
  crawled_at DATETIME      DEFAULT CURRENT_TIMESTAMP COMMENT '采集时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_text_hash (text_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='名言采集结果表';
